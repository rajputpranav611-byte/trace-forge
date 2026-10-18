import logging
from typing import Optional
from falkordb import FalkorDB
from app.core.config import get_settings

logger = logging.getLogger("traceforge.db")


class FalkorDBClient:
    """Singleton connection holder for FalkorDB."""

    def __init__(self) -> None:
        self._client: Optional[FalkorDB] = None

    def connect(self) -> None:
        settings = get_settings()
        try:
            self._client = FalkorDB(
                host=settings.FALKORDB_HOST,
                port=settings.FALKORDB_PORT,
            )
            # Ping connection by retrieving graph instance
            graph = self._client.select_graph(settings.FALKORDB_GRAPH_NAME)
            logger.info(
                f"Connected to FalkorDB at {settings.FALKORDB_HOST}:{settings.FALKORDB_PORT}, graph: {settings.FALKORDB_GRAPH_NAME}"
            )
        except Exception as exc:
            logger.error(f"Failed to connect to FalkorDB: {exc}")
            self._client = None
            raise

    def get_client(self) -> FalkorDB:
        if self._client is None:
            self.connect()
        return self._client

    def get_graph(self, graph_name: Optional[str] = None):
        client = self.get_client()
        name = graph_name or get_settings().FALKORDB_GRAPH_NAME
        return client.select_graph(name)

    def check_health(self) -> dict:
        """Executes a lightweight Cypher query to verify live database response."""
        settings = get_settings()
        try:
            client = self.get_client()
            graph = client.select_graph(settings.FALKORDB_GRAPH_NAME)
            result = graph.query("RETURN 1 AS ping")
            if result.result_set and result.result_set[0][0] == 1:
                return {
                    "connected": True,
                    "host": settings.FALKORDB_HOST,
                    "port": settings.FALKORDB_PORT,
                    "graph": settings.FALKORDB_GRAPH_NAME,
                    "query_response": "ok",
                }
            return {
                "connected": False,
                "error": "Unexpected response from FalkorDB ping query",
            }
        except Exception as exc:
            return {
                "connected": False,
                "error": str(exc),
                "host": settings.FALKORDB_HOST,
                "port": settings.FALKORDB_PORT,
            }


db_client = FalkorDBClient()
