from functools import wraps

from flask import request, jsonify, g
from marshmallow import Schema, ValidationError


def validate_schema(schema: Schema):
    """
    Creates a decorator that validates ``request.json`` against a
    Marshmallow schema.  Returns HTTP 400 when validation fails.
    """

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            json_body = request.get_json(silent=True)
            if json_body is None:
                return jsonify(
                    {"message": "Validation failed", "errors": "Request body must be valid JSON"}
                ), 400

            try:
                validated = schema.load(json_body)
            except ValidationError as err:
                return jsonify(
                    {"message": "Validation failed", "errors": err.normalized_messages()}
                ), 400

            # store validated data on the flask.g object to avoid assigning
            # arbitrary attributes to the Request object (which static
            # type checkers may flag)
            g.validated_body = validated
            return f(*args, **kwargs)

        return wrapper

    return decorator
