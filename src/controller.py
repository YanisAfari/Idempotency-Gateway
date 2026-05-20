import time

from flask import request, jsonify


def process_payment():
    """
    Simulates payment processing and returns a success response after ~2 seconds.
    """
    body = getattr(request, "_validated_body", None) or request.get_json(silent=True) or {}
    amount = body['amount']
    time.sleep(10)
    return jsonify({
        "success": True,
        "message": f"Charged {amount} {body['currency']}",
    }), 200
