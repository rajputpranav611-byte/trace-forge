from unittest.mock import patch, MagicMock
import pytest
from app.core.config import Settings
from app.db.client import FalkorDBClient


def test_falkordb_default_settings():
    """Verify local development defaults remain unchanged."""
    settings = Settings(
        _env_file=None,
        FALKORDB_HOST="localhost",
        FALKORDB_PORT=6379,
        FALKORDB_GRAPH_NAME="traceforge",
        FALKORDB_USERNAME="",
        FALKORDB_PASSWORD="",
        FALKORDB_SSL=False,
    )
    assert settings.FALKORDB_HOST == "localhost"
    assert settings.FALKORDB_PORT == 6379
    assert settings.FALKORDB_GRAPH_NAME == "traceforge"
    assert settings.FALKORDB_USERNAME == ""
    assert settings.FALKORDB_PASSWORD == ""
    assert settings.FALKORDB_SSL is False


def test_falkordb_hosted_settings_overrides():
    """Verify settings parse hosted FalkorDB environment configurations."""
    settings = Settings(
        _env_file=None,
        FALKORDB_HOST="test-falkordb.cloud",
        FALKORDB_PORT=53888,
        FALKORDB_GRAPH_NAME="traceforge",
        FALKORDB_USERNAME="falkordb",
        FALKORDB_PASSWORD="secret-password-mock",
        FALKORDB_SSL=True,
    )
    assert settings.FALKORDB_HOST == "test-falkordb.cloud"
    assert settings.FALKORDB_PORT == 53888
    assert settings.FALKORDB_USERNAME == "falkordb"
    assert settings.FALKORDB_PASSWORD == "secret-password-mock"
    assert settings.FALKORDB_SSL is True


def test_client_connect_local_defaults():
    """Verify FalkorDBClient connects without extra credentials on local setup."""
    mock_settings = Settings(
        _env_file=None,
        FALKORDB_HOST="localhost",
        FALKORDB_PORT=6379,
        FALKORDB_GRAPH_NAME="traceforge",
        FALKORDB_USERNAME="",
        FALKORDB_PASSWORD="",
        FALKORDB_SSL=False,
    )
    client_instance = FalkorDBClient()

    with patch("app.db.client.get_settings", return_value=mock_settings):
        with patch("app.db.client.FalkorDB") as mock_falkordb_cls:
            mock_db = MagicMock()
            mock_falkordb_cls.return_value = mock_db

            client_instance.connect()

            mock_falkordb_cls.assert_called_once_with(
                host="localhost",
                port=6379,
                ssl=False,
                socket_timeout=10,
                socket_connect_timeout=10,
            )
            mock_db.select_graph.assert_called_once_with("traceforge")


def test_client_connect_hosted_configuration():
    """Verify FalkorDBClient securely forwards username, password, and ssl for hosted instances."""
    mock_settings = Settings(
        _env_file=None,
        FALKORDB_HOST="hosted-db.falkordb.cloud",
        FALKORDB_PORT=53888,
        FALKORDB_GRAPH_NAME="traceforge",
        FALKORDB_USERNAME="falkordb",
        FALKORDB_PASSWORD="mock-secure-token",
        FALKORDB_SSL=True,
    )
    client_instance = FalkorDBClient()

    with patch("app.db.client.get_settings", return_value=mock_settings):
        with patch("app.db.client.FalkorDB") as mock_falkordb_cls:
            mock_db = MagicMock()
            mock_falkordb_cls.return_value = mock_db

            client_instance.connect()

            mock_falkordb_cls.assert_called_once_with(
                host="hosted-db.falkordb.cloud",
                port=53888,
                ssl=True,
                socket_timeout=10,
                socket_connect_timeout=10,
                username="falkordb",
                password="mock-secure-token",
            )
            mock_db.select_graph.assert_called_once_with("traceforge")
