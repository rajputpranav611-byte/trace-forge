import urllib.request
import json

url = "http://127.0.0.1:8000/api/v1/surgery/simulate"
payload = {
    "baseline_incident_id": "INC-2026-8821",
    "experiment_name": "Test Sever Database Dependency",
    "actions": [
        {
            "action_type": "remove_dependency",
            "source_id": "payment-core",
            "target_id": "payment-db-cluster",
            "relationship_type": "DEPENDS_ON",
            "justification": "Sever database to isolate if payment-core connection pool exhaustion is root cause"
        }
    ]
}

req = urllib.request.Request(
    url,
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)
with urllib.request.urlopen(req) as response:
    status_code = response.getcode()
    body = response.read().decode("utf-8")
    print(f"Status Code: {status_code}")
    data = json.loads(body)
    print("Experiment ID:", data["experiment_id"])
    print("Actions applied count:", len(data["actions_applied"]))
    print("Causal Explanation:", data["causal_change_explanation"])
    print("Blast Radius Diff:", data["blast_radius_diff"])
    print("Hypothesis Diffs Count:", len(data["hypothesis_diffs"]))
    for d in data["hypothesis_diffs"]:
        print(f" - {d['title']}: baseline rank {d['baseline_rank']} ({d['baseline_score']}) -> exp rank {d['experiment_rank']} ({d['experiment_score']}), delta={d['score_delta']}")
