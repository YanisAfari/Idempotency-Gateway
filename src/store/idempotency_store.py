import threading
import time
from typing import TypedDict


class IdempotencyRecord(TypedDict):
    created_at: float
    response: dict


class InMemoryIdempotencyStore:
    """
    In-memory idempotency store with:
    - TTL expiration
    - request coalescing
    - background cleanup
    """

    CLEANUP_INTERVAL_SECONDS = 3600

    def __init__(self, ttl_ms: int = 24 * 60 * 60 * 1000):
        self._records: dict[str, IdempotencyRecord] = {}
        self._in_flight: dict[str, threading.Event] = {}

        self._ttl_seconds = ttl_ms / 1000

        self._lock = threading.Lock()

        self._shutdown = threading.Event()

        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            daemon=True,
        )
        self._cleanup_thread.start()

    # ------------------------------------------------------------------
    # Idempotency methods
    # ------------------------------------------------------------------

    def get(self, key: str) -> dict | None:
        now = time.monotonic()

        with self._lock:
            record = self._records.get(key)

            if record is None:
                return None

            if now - record["created_at"] > self._ttl_seconds:
                del self._records[key]
                return None

            return record["response"]

    def set(self, key: str, record: dict) -> None:
        with self._lock:
            self._records[key] = {
                "created_at": time.monotonic(),
                "response": record,
            }

    # ------------------------------------------------------------------
    # Request coalescing methods
    # ------------------------------------------------------------------

    def begin(self, key: str) -> None:
        with self._lock:
            self._in_flight.setdefault(key, threading.Event())

    def wait(self, key: str, timeout: float = 10.0) -> bool:
        with self._lock:
            event = self._in_flight.get(key)

        if event is None:
            return False

        return event.wait(timeout)

    def complete(self, key: str) -> None:
        with self._lock:
            event = self._in_flight.pop(key, None)

        if event is not None:
            event.set()

    # ------------------------------------------------------------------
    # Lifecycle methods
    # ------------------------------------------------------------------

    def clear(self) -> None:
        with self._lock:
            events = list(self._in_flight.values())

            self._records.clear()
            self._in_flight.clear()

        for event in events:
            event.set()

    def stop(self) -> None:
        self._shutdown.set()
        self._cleanup_thread.join(timeout=1)

    # ------------------------------------------------------------------
    # Internal cleanup
    # ------------------------------------------------------------------

    def _cleanup_loop(self) -> None:
        while not self._shutdown.wait(
            self.CLEANUP_INTERVAL_SECONDS
        ):
            self._cleanup_expired()

    def _cleanup_expired(self) -> None:
        now = time.monotonic()

        with self._lock:
            expired_keys = [
                key
                for key, record in self._records.items()
                if now - record["created_at"] > self._ttl_seconds
            ]

            for key in expired_keys:
                del self._records[key]


idempotency_store = InMemoryIdempotencyStore()