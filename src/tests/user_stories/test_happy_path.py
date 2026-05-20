import time
import uuid

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


def test_user_story_1_processes_first_transaction_with_expected_response(client):
    """User Story 1: processes first transaction with expected response"""
    key = str(uuid.uuid4())
    start = time.monotonic()

    response = client.post(
        "/process-payment",
        json={"amount": 100, "currency": "GHS"},
        headers={"Idempotency-Key": key},
    )

    elapsed_ms = (time.monotonic() - start) * 1000

    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "message": "Charged 100 GHS",
    }
    assert elapsed_ms >= 1900, f"Expected ~2s processing delay, got {elapsed_ms:.0f}ms"
