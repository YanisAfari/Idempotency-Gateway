import time
from decimal import Decimal

from flask import request, jsonify, g


def _format_amount(amount):
    """Render a Decimal as the user would expect to see it: 100 stays "100",
    100.5 stays "100.5". Falls through unchanged for plain ints/floats."""
    if isinstance(amount, Decimal):
        # Integral Decimal → int; fractional Decimal → float
        if amount == amount.to_integral_value():
            return int(amount)
        return float(amount)
    return amount


def process_payment():
    """
    Simulates payment processing and returns a success response after ~2 seconds.

    Reads the *validated* body from ``flask.g`` (populated by the validation
    middleware) so that normalized values — Decimal amounts, uppercased
    currency codes — flow through to the response. Falls back to the raw
    JSON only if validation didn't run for some reason.
    """
    body = getattr(g, "validated_body", None) or request.get_json(silent=True) or {}
    amount = _format_amount(body['amount'])
    time.sleep(2)
    return jsonify({
        "success": True,
        "message": f"Charged {amount} {body['currency']}",
    }), 200
