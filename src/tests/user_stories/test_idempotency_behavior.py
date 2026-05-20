import time
import uuid
import threading
from datetime import datetime, timezone, timedelta

import pytest

from src.app import app
from src.store.idempotency_store import idempotency_store


@pytest.fixture(autouse=True)
def clear_stores():
    idempotency_store.clear()
    yield
    idempotency_store.clear()


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_user_story_2_duplicate_request_returns_cached_response_without_reprocessing(client):
    """User Story 2: duplicate request returns cached response without re-processing"""
    key = str(uuid.uuid4())
    payload = {"amount": 100, "currency": "GHS"}

    first_start = time.monotonic()
    first_response = client.post(
        "/process-payment",
        json=payload,
        headers={"Idempotency-Key": key},
    )
    first_elapsed_ms = (time.monotonic() - first_start) * 1000

    second_start = time.monotonic()
    second_response = client.post(
        "/process-payment",
        json=payload,
        headers={"Idempotency-Key": key},
    )
    second_elapsed_ms = (time.monotonic() - second_start) * 1000

    assert first_response.status_code == 200
    assert second_response.status_code == first_response.status_code
    assert second_response.get_json() == first_response.get_json()
    assert second_response.headers.get("X-Cache-Hit") == "true"

    assert first_elapsed_ms >= 1900, f"Expected first request to take ~2s, got {first_elapsed_ms:.0f}ms"
    assert second_elapsed_ms < 500, f"Expected replay to be fast, got {second_elapsed_ms:.0f}ms"


def test_user_story_3_same_key_with_different_payload_is_rejected(client):
    """User Story 3: same key with different payload is rejected"""
    key = str(uuid.uuid4())

    client.post(
        "/process-payment",
        json={"amount": 100, "currency": "GHS"},
        headers={"Idempotency-Key": key},
    )

    conflict_response = client.post(
        "/process-payment",
        json={"amount": 500, "currency": "GHS"},
        headers={"Idempotency-Key": key},
    )

    assert conflict_response.status_code == 422
    assert conflict_response.get_json()["message"] == (
        "Idempotency key already used for a different request body."
    )


def test_bonus_in_flight_duplicate_waits_and_reuses_original_response():
    """Bonus story: in-flight duplicate waits and reuses original response"""
    app.config["TESTING"] = True
    key = str(uuid.uuid4())
    payload = {"amount": 100, "currency": "GHS"}
    results = [None, None]

    def make_request(index):
        with app.test_client() as c:
            results[index] = c.post(
                "/process-payment",
                json=payload,
                headers={"Idempotency-Key": key},
            )

    start = time.monotonic()

    t1 = threading.Thread(target=make_request, args=(0,))
    t2 = threading.Thread(target=make_request, args=(1,))
    t1.start()
    time.sleep(0.05)  # Small offset so t1 registers first
    t2.start()

    t1.join(timeout=10)
    t2.join(timeout=10)

    elapsed_ms = (time.monotonic() - start) * 1000

    response_a = results[0]
    response_b = results[1]

    assert response_a.status_code == 200
    assert response_b.status_code == 200
    assert response_b.get_json() == response_a.get_json()
    assert response_b.headers.get("X-Cache-Hit") == "true"

    assert elapsed_ms >= 1900, f"Expected coalesced flow to wait for first request, got {elapsed_ms:.0f}ms"
    assert elapsed_ms < 4500, f"Expected no double processing delay, got {elapsed_ms:.0f}ms"


def test_expired_idempotency_key_is_removed_on_access():
    """Expired idempotency key is removed on access (TTL)"""
    idempotency_store.set("expired-key", {
        "requestHash": "hash",
        "createdAt": datetime.now(timezone.utc) - timedelta(hours=25),
    })

    expired = idempotency_store.get("expired-key")
    assert expired is None
    assert idempotency_store.get("expired-key") is None
