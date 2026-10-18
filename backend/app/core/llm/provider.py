import abc
import json
import logging
from typing import Optional, Tuple
import httpx
from app.core.config import get_settings
from app.schemas.investigation import InvestigationContextResponse
from app.schemas.hypotheses import LLMHypothesisOutput
from app.core.llm.fallback import generate_deterministic_fallback_hypotheses

logger = logging.getLogger("traceforge.llm.provider")


class LLMProvider(abc.ABC):
    """Abstract interface for LLM hypothesis providers."""

    @abc.abstractmethod
    async def generate_hypotheses(
        self,
        context: InvestigationContextResponse,
    ) -> Tuple[LLMHypothesisOutput, str, bool]:
        """Generates candidate hypotheses from bounded graph context.

        Returns: (LLMHypothesisOutput, model_name, is_fallback)
        """
        pass


class GeminiProvider(LLMProvider):
    """Google Gemini API provider using official REST endpoint with structured outputs."""

    def __init__(self, api_key: str, model: str = "gemini-1.5-flash", timeout: float = 8.0) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    async def generate_hypotheses(
        self,
        context: InvestigationContextResponse,
    ) -> Tuple[LLMHypothesisOutput, str, bool]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"

        prompt = _build_prompt(context)
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "response_mime_type": "application/json",
            },
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
            parsed = json.loads(raw_text)
            validated = LLMHypothesisOutput.model_validate(parsed)
            return validated, self.model, False


class OpenAIProvider(LLMProvider):
    """OpenAI API provider using standard chat completions format."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini", timeout: float = 8.0) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    async def generate_hypotheses(
        self,
        context: InvestigationContextResponse,
    ) -> Tuple[LLMHypothesisOutput, str, bool]:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}"}

        prompt = _build_prompt(context)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are an expert site reliability and root cause analysis engineer. Output only valid JSON conforming strictly to the requested schema."},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            raw_text = data["choices"][0]["message"]["content"]
            parsed = json.loads(raw_text)
            validated = LLMHypothesisOutput.model_validate(parsed)
            return validated, self.model, False


class FallbackProvider(LLMProvider):
    """Deterministic, graph-grounded rule provider used when no API keys are configured or APIs fail."""

    async def generate_hypotheses(
        self,
        context: InvestigationContextResponse,
    ) -> Tuple[LLMHypothesisOutput, str, bool]:
        return generate_deterministic_fallback_hypotheses(context), "deterministic-fallback-v1", True


def get_llm_provider() -> LLMProvider:
    """Factory selecting the best available LLM provider based on environment credentials."""
    settings = get_settings()
    pref = settings.LLM_PROVIDER.lower()

    if pref == "gemini" and settings.GEMINI_API_KEY:
        return GeminiProvider(settings.GEMINI_API_KEY, settings.LLM_MODEL, settings.LLM_TIMEOUT_SECONDS)
    elif pref == "openai" and settings.OPENAI_API_KEY:
        return OpenAIProvider(settings.OPENAI_API_KEY, "gpt-4o-mini", settings.LLM_TIMEOUT_SECONDS)
    elif pref == "auto":
        if settings.GEMINI_API_KEY:
            return GeminiProvider(settings.GEMINI_API_KEY, settings.LLM_MODEL, settings.LLM_TIMEOUT_SECONDS)
        elif settings.OPENAI_API_KEY:
            return OpenAIProvider(settings.OPENAI_API_KEY, "gpt-4o-mini", settings.LLM_TIMEOUT_SECONDS)

    # Default to deterministic fallback
    return FallbackProvider()


def _build_prompt(context: InvestigationContextResponse) -> str:
    """Constructs a compact, bounded prompt containing strictly verifiable graph records."""
    inc = context.incident
    alerts_summary = [
        {"id": a.id, "service": a.service_id, "name": a.name, "severity": a.severity, "desc": a.description}
        for a in context.alerts
    ]
    metrics_summary = [
        {"id": m.id, "alert_id": m.alert_id, "metric": m.metric_name, "value": m.value, "baseline": m.baseline, "deviation": f"+{m.deviation_sigma}σ"}
        for m in context.metrics
    ]
    deployments_summary = [
        {"id": d.id, "service": d.service_id, "version": d.version, "deployed_at": d.deployed_at, "strategy": d.strategy}
        for d in context.deployments
    ]
    paths_summary = [
        {"length": p.length, "node_ids": p.node_ids}
        for p in context.topology.traversed_paths[:5]
    ]

    return f"""
You are the TraceForge incident root cause analysis engine.
Analyze the following operational incident graph data:

INCIDENT:
ID: {inc.id}
Title: {inc.title}
Severity: {inc.severity}
Summary: {inc.summary}

ALERTS:
{json.dumps(alerts_summary, indent=2)}

METRIC ANOMALIES:
{json.dumps(metrics_summary, indent=2)}

CANDIDATE PRODUCTION DEPLOYMENTS:
{json.dumps(deployments_summary, indent=2)}

TRAVERSED CAUSAL PATHS:
{json.dumps(paths_summary, indent=2)}

CRITICAL INSTRUCTIONS:
1. Generate between 1 and 3 competing hypotheses.
2. In 'supporting_evidence_ids' and 'contradicting_evidence_ids', you MUST ONLY include exact record IDs present above (e.g. ALT-101, MET-501, DEP-4012).
3. Do NOT invent or hallucinate evidence IDs. Unknown IDs will be rejected.
4. Do not declare that any hypothesis is definitely proven; formulate candidate explanations with confidence scores (0.0 to 1.0).

OUTPUT SCHEMA (JSON):
{{
  "hypotheses": [
    {{
      "id": "HYP-01",
      "title": "string",
      "statement": "string",
      "suspected_entity": "string",
      "confidence": 0.85,
      "supporting_evidence_ids": ["ALT-101", "DEP-4012"],
      "contradicting_evidence_ids": ["ALT-105"],
      "recommended_action": "string or null"
    }}
  ],
  "reasoning_summary": "string"
}}
"""
