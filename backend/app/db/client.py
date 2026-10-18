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
            falkordb_kwargs = {
                "host": settings.FALKORDB_HOST,
                "port": settings.FALKORDB_PORT,
                "ssl": settings.FALKORDB_SSL,
                "socket_timeout": 10,
                "socket_connect_timeout": 10,
            }
            if settings.FALKORDB_USERNAME:
                falkordb_kwargs["username"] = settings.FALKORDB_USERNAME
            if settings.FALKORDB_PASSWORD:
                falkordb_kwargs["password"] = settings.FALKORDB_PASSWORD

            self._client = FalkorDB(**falkordb_kwargs)
            # Ping connection by retrieving graph instance
            graph = self._client.select_graph(settings.FALKORDB_GRAPH_NAME)
            logger.info(
                f"Connected to FalkorDB at {settings.FALKORDB_HOST}:{settings.FALKORDB_PORT}, graph: {settings.FALKORDB_GRAPH_NAME}, ssl: {settings.FALKORDB_SSL}"
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
