import threading


class RequestCoalescerStore:
    """
    Tracks in-flight requests and lets concurrent duplicates wait for the
    original to complete instead of executing duplicate work.
    """

    def __init__(self):
        self._in_flight: dict[str, threading.Event] = {}
        self._lock = threading.Lock()

    def begin(self, key: str) -> None:
        """
        Marks a key as in-flight if it does not already exist.
        """
        with self._lock:
            self._in_flight.setdefault(key, threading.Event())

    def wait(self, key: str, timeout: float = 10.0) -> bool:
        """
        Waits for the in-flight request to complete.

        Returns:
            False -> no request was in-flight
            True  -> waited (or event already completed)
        """
        with self._lock:
            event = self._in_flight.get(key)

        if event is None:
            return False

        event.wait(timeout=timeout)
        return True

    def complete(self, key: str) -> None:
        """
        Completes and removes the in-flight request.
        """
        with self._lock:
            event = self._in_flight.pop(key, None)

        if event is not None:
            event.set()

    def clear(self) -> None:
        """
        Clears all in-flight entries and releases waiters.
        """
        with self._lock:
            events = list(self._in_flight.values())
            self._in_flight.clear()

        for event in events:
            event.set()


request_coalescer_store = RequestCoalescerStore()