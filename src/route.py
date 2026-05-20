from flask import Blueprint, jsonify

from .controller import process_payment
from .middleware.validation_middleware import validate_schema
from .middleware.idempotency_middleware import idempotency_middleware
from .schema import request_schema

router = Blueprint("router", __name__)


# Health check endpoint
@router.route("/health", methods=["GET"])
def health():
    return jsonify({"success": True}), 200


@router.route("/process-payment", methods=["POST"])
@validate_schema(request_schema)
@idempotency_middleware()
def handle_process_payment():
    return process_payment()
