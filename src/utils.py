import hashlib
import json

from flask import Response, jsonify


def hash_request(body: dict) -> str:
    """
    Produces a stable SHA-256 hash for a request body payload.
    """
    content = json.dumps(body, separators=(",", ":"), sort_keys=True) if body else ""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def replay_cached_response(cached: dict) -> Response:
    """
    Replays a cached HTTP response and marks it as a cache hit.
    """
    response = jsonify(cached["body"])
    response.status_code = cached["statusCode"]

    for key, value in cached.get("headers", {}).items():
        if value is None:
            continue
        if isinstance(value, list):
            for v in value:
                response.headers.add(key, v)
            continue
        response.headers[key] = str(value)

    response.headers["X-Cache-Hit"] = "true"
    return response
