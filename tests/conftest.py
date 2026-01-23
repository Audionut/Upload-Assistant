import contextlib
import importlib
import json
import os
import time
from collections.abc import Generator
from typing import Any

import keyring
import pytest

# Use the provided bearer token for tests that exercise API bearer auth.
# Tests may set `UA_TEST_BEARER_TOKEN` in their environment. Do NOT set
# `UA_TOKEN` here (that causes the server to delete the persisted token
# store on import). Instead, inject the test token into the keyring token
# store and restore the original value after the test session.
TEST_BEARER_TOKEN = os.environ.get("UA_TEST_BEARER_TOKEN", "")


@pytest.fixture(scope="session", autouse=True)
def test_env() -> Generator[None, None, None]:
    os.environ.setdefault("UA_WEBUI_USERNAME", "testuser")
    # Ensure DOCKER_CONTAINER not set so keyring fallback isn't forced in test env
    os.environ.setdefault("DOCKER_CONTAINER", "")

    orig_store = None
    token_key = "upload-assistant-api-tokens"
    if TEST_BEARER_TOKEN:
        try:
            with contextlib.suppress(Exception):
                orig_store = keyring.get_password("upload-assistant", token_key)
            # Load existing store if present, else start fresh
            store = {}
            if orig_store:
                try:
                    parsed = json.loads(orig_store)
                    if isinstance(parsed, dict):
                        store = parsed
                except Exception:
                    store = {}
            # Insert test token (use TEST_BEARER_TOKEN as id)
            store[TEST_BEARER_TOKEN] = {
                "user": os.environ.get("UA_WEBUI_USERNAME", "testuser"),
                "label": "test",
                "created": int(time.time()),
                "expiry": None,
                "scopes": ["*"]
            }
            with contextlib.suppress(Exception):
                keyring.set_password("upload-assistant", token_key, json.dumps(store, separators=(',', ':')))
        except Exception:
            # Non-fatal; tests that rely on bearer token may fail if injection fails
            pass

    yield

    # Restore original token store after tests
    if TEST_BEARER_TOKEN:
        try:
            with contextlib.suppress(Exception):
                if orig_store is None:
                    keyring.delete_password("upload-assistant", token_key)
                else:
                    keyring.set_password("upload-assistant", token_key, orig_store)
        except Exception:
            pass


@pytest.fixture(scope="module")
def client() -> Generator[Any, None, Any]:
    # Import here so environment is configured first
    import web_ui.server as server

    # Reload to ensure any env changes are picked up in case tests mutate env
    importlib.reload(server)

    with server.app.test_client() as c:
        yield c
