import importlib
import os
from collections.abc import Generator
from typing import Any

import pytest

# Use the provided bearer token for tests that exercise API bearer auth.
# Set environment variables before importing the server module so the
# token store and owner are available at import time.
TEST_BEARER_TOKEN = os.environ.get("UA_TEST_BEARER_TOKEN", "")


@pytest.fixture(scope="session", autouse=True)
def test_env() -> Generator[None, None, None]:
    # Provide a UA_TOKEN (single-token mode) and a username to associate with it.
    os.environ.setdefault("UA_TOKEN", TEST_BEARER_TOKEN)
    os.environ.setdefault("UA_WEBUI_USERNAME", "testuser")
    # Ensure DOCKER_CONTAINER not set so keyring fallback isn't forced in test env
    os.environ.setdefault("DOCKER_CONTAINER", "")
    yield


@pytest.fixture(scope="module")
def client() -> Generator[Any, None, Any]:
    # Import here so environment is configured first
    import web_ui.server as server

    # Reload to ensure any env changes are picked up in case tests mutate env
    importlib.reload(server)

    with server.app.test_client() as c:
        yield c
