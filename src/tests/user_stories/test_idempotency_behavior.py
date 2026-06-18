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


def test_expired_idempotency_key_is_removed_on_access(monkeypatch):
    """Expired idempotency key is removed on access (TTL).

    The store uses ``time.monotonic()`` as its clock (immune to wall-clock
    jumps), so we simulate the passage of 25 hours by patching ``monotonic``
    inside the store module — directly injecting a 25-hour-old datetime into
    the record wouldn't work, because the store stamps its own monotonic
    time at write time.
    """
    from src.store import idempotency_store as store_module

    idempotency_store.set("expired-key", {"requestHash": "hash"})

    # Advance the store's clock by 25 hours (TTL is 24h)
    fake_now = time.monotonic() + (25 * 60 * 60)
    monkeypatch.setattr(store_module.time, "monotonic", lambda: fake_now)

    expired = idempotency_store.get("expired-key")
    assert expired is None
    assert idempotency_store.get("expired-key") is None


def test_validated_body_reaches_controller(client):
    """The controller receives the *normalized* body (uppercased currency)
    from the validation middleware, not the raw JSON."""
    key = str(uuid.uuid4())

    response = client.post(
        "/process-payment",
        json={"amount": 100, "currency": "ghs"},  # lowercase on the wire
        headers={"Idempotency-Key": key},
    )

    assert response.status_code == 200
    # If the validated body reaches the controller, the currency is uppercased.
    assert response.get_json()["message"] == "Charged 100 GHS"


def test_failed_first_attempt_releases_key_for_retry(client, monkeypatch):
    """If the first request raises, the response-less record is evicted so
    a retry with the same key can proceed, instead of being locked out."""
    from src import controller

    key = str(uuid.uuid4())
    payload = {"amount": 100, "currency": "GHS"}

    # First attempt: force the controller to blow up after the store record
    # has been created (simulating a transient downstream failure).
    original = controller.process_payment
    call_count = {"n": 0}

    def flaky_process_payment():
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("simulated downstream failure")
        return original()

    monkeypatch.setattr(controller, "process_payment", flaky_process_payment)

    # First request should bubble the error up (500 from Flask's default
    # error handler is fine; we just need it to fail).
    try:
        client.post(
            "/process-payment",
            json=payload,
            headers={"Idempotency-Key": key},
        )
    except RuntimeError:
        pass  # the error may propagate in test client depending on config

    # Second request with the SAME key + body should now succeed, because
    # the poisoned record was evicted on the first attempt's exception.
    second = client.post(
        "/process-payment",
        json=payload,
        headers={"Idempotency-Key": key},
    )

    assert second.status_code == 200, (
        f"Retry was locked out by a stale poisoned record: got {second.status_code} "
        f"with body {second.get_json()}"
    )
    assert second.get_json()["message"] == "Charged 100 GHS"
