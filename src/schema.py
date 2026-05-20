from decimal import Decimal, InvalidOperation
import iso4217
import uuid

from marshmallow import (
    Schema,
    fields,
    validates,
    ValidationError,
    post_load,
)


def _is_valid_currency_code(code: str) -> bool:
    try:
        iso4217.Currency(code.upper())
        return True
    except ValueError:
        return False

import uuid

def is_valid_uuid(val):
    try:
        # Attempt to create a UUID object
        uuid.UUID(str(val))
        return True
    except ValueError:
        # If it fails, the string is not a valid UUID
        return False


class RequestSchema(Schema):
    amount = fields.Raw(required=True)
    currency = fields.String(required=True)

    @validates("amount")
    def validate_amount(self, value):
        # Reject bool explicitly
        if isinstance(value, bool):
            raise ValidationError("Amount must be a number")

        # Reject strings like "12.34"
        if isinstance(value, str):
            raise ValidationError("Amount must be a number")

        # Accept only JSON numeric types
        if not isinstance(value, (int, float)):
            raise ValidationError("Amount must be a number")

        try:
            decimal_value = Decimal(str(value))
        except InvalidOperation:
            raise ValidationError("Invalid amount")

        if decimal_value < 0:
            raise ValidationError("Amount must be positive")

        if decimal_value.quantize(Decimal("0.01")) != decimal_value:
            raise ValidationError(
                "Amount must have at most 2 decimal places"
            )

    @validates("currency")
    def validate_currency(self, value):
        trimmed = value.strip().upper()

        if not _is_valid_currency_code(trimmed):
            raise ValidationError(
                "Invalid ISO 4217 currency code"
            )

    @post_load
    def normalize(self, data, **kwargs):
        data["currency"] = data["currency"].strip().upper()
        data["amount"] = Decimal(str(data["amount"]))
        return data


request_schema = RequestSchema()