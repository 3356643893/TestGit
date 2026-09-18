import pytest
from core.api_client import ApiClient
from utils.token_cache import load_token_from_cache, save_token_to_cache
from utils.mock_handler import activate_mock, deactivate_mock


@pytest.fixture(scope="session")
def api_client():
    """pytest fixture"""
    client = ApiClient()
    cached_token = load_token_from_cache()
    if cached_token:
        client.set_token(cached_token)
    yield client
    if client.token:
        save_token_to_cache(client.token)


@pytest.fixture(scope="function")
def db():
    """pytest fixture"""
    from core.db_handler import DBHandler
    db = DBHandler()
    yield db
    db.rollback()
    db.close()


@pytest.fixture(autouse=True)
def auto_mock():
    """pytest fixture"""
    from config.config import config
    mock_cfg = config.get("mock", {})
    if mock_cfg.get("enabled"):
        activate_mock()
    yield
    deactivate_mock()