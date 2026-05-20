from functools import wraps
from ..schema import is_valid_uuid

from flask import request

from ..store.idempotency_store import idempotency_store
from ..utils import hash_request, replay_cached_response

from flask import jsonify
from datetime import datetime, timezone



def idempotency_middleware():
    """
    Enforces idempotency for payment requests.

    - Validates the ``Idempotency-Key`` header.
    - Replays cached responses for duplicates.
    - Rejects key reuse with different payloads.
    - Coalesces concurrent in-flight requests for the same key.
    """

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            key_header = request.headers.get("Idempotency-Key")

            if not key_header:
                return jsonify({
                    "error": "Missing idempotency key",
                    "message": "The Idempotency-Key header is required for POST requests",
                }), 400

            if not is_valid_uuid(key_header):
                return jsonify({
                    "error": "Invalid idempotency key format",
                    "message": "Key must be 16-64 alphanumeric characters, hyphens, or underscores",
                }), 400

            composite_key = f"{request.method}:{request.path}:{key_header}"
            # Ensure we pass a dict to hash_request; get_json may return None
            request_body = request.get_json(silent=True) or {}
            request_hash = hash_request(request_body)

            existing = idempotency_store.get(composite_key)

            if existing:
                if existing["requestHash"] != request_hash:
                    return jsonify({
                        "message": "Idempotency key already used for a different request body.",
                    }), 422

                if existing.get("response"):
                    return replay_cached_response(existing["response"])

                # In-flight coalescing: wait for the original to finish
                idempotency_store.wait(composite_key)

                completed = idempotency_store.get(composite_key)

                if completed and completed.get("response"):
                    return replay_cached_response(completed["response"])

                return jsonify({
                    "error": "Request could not be replayed",
                    "message": "Original request did not complete successfully",
                }), 500

            created_at = datetime.now(timezone.utc)

            idempotency_store.set(composite_key, {
                "requestHash": request_hash,
                "createdAt": created_at,
            })
            idempotency_store.begin(composite_key)

            try:
                response = f(*args, **kwargs)

                # Capture the response for future replays
                if hasattr(response, "get_json"):
                    body = response.get_json(silent=True)
                    status_code = response.status_code
                else:
                    # Tuple response (body, status_code)
                    from flask import make_response as _mr
                    response = _mr(response)
                    body = response.get_json(silent=True)
                    status_code = response.status_code

                idempotency_store.set(composite_key, {
                    "requestHash": request_hash,
                    "response": {
                        "body": body,
                        "statusCode": status_code,
                        "headers": dict(response.headers),
                    },
                    "createdAt": created_at,
                    "completedAt": datetime.now(timezone.utc),
                })
                idempotency_store.complete(composite_key)

                return response

            except Exception:
                idempotency_store.complete(composite_key)
                raise

        return wrapper

    return decorator
