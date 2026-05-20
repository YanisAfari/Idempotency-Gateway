open_api_spec = {
    "openapi": "3.0.3",
    "info": {
        "title": "Idempotency Gateway API",
        "version": "1.0.0",
        "description": "Flask API that prevents duplicate payment processing using idempotency keys.",
    },
    "servers": [
        {
            "url": "http://localhost:3000",
            "description": "Local development",
        },
    ],
    "tags": [
        {"name": "Health", "description": "Service health"},
        {"name": "Payments", "description": "Payment processing"},
    ],
    "paths": {
        "/health": {
            "get": {
                "tags": ["Health"],
                "summary": "Health check",
                "responses": {
                    "200": {
                        "description": "Service is healthy",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "success": {"type": "boolean", "example": True},
                                    },
                                    "required": ["success"],
                                },
                            },
                        },
                    },
                },
            },
        },
        "/process-payment": {
            "post": {
                "tags": ["Payments"],
                "summary": "Process a payment with idempotency protection",
                "description": "Validates request payload, enforces idempotency via Idempotency-Key header, and returns cached responses for safe retries.",
                "parameters": [
                    {
                        "in": "header",
                        "name": "Idempotency-Key",
                        "required": True,
                        "schema": {
                            "type": "string",
                            "format": "uuid",
                        },
                        "description": "Unique idempotency key per logical payment request.",
                    },
                ],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "$ref": "#/components/schemas/ProcessPaymentRequest",
                            },
                            "examples": {
                                "sample": {
                                    "value": {
                                        "amount": 100,
                                        "currency": "GHS",
                                    },
                                },
                            },
                        },
                    },
                },
                "responses": {
                    "200": {
                        "description": "Payment processed (or replayed from cache)",
                        "headers": {
                            "X-Cache-Hit": {
                                "description": "Present with value 'true' when response is replayed from idempotency cache.",
                                "schema": {"type": "string", "example": "true"},
                            },
                        },
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/ProcessPaymentSuccess",
                                },
                            },
                        },
                    },
                    "400": {
                        "description": "Validation error, missing idempotency key, or invalid idempotency key format",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "oneOf": [
                                        {"$ref": "#/components/schemas/ValidationErrorResponse"},
                                        {"$ref": "#/components/schemas/IdempotencyHeaderErrorResponse"},
                                    ],
                                },
                            },
                        },
                    },
                    "422": {
                        "description": "Idempotency key reused with a different request body",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/IdempotencyConflictResponse",
                                },
                            },
                        },
                    },
                    "500": {
                        "description": "In-flight replay fallback failure",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/ReplayFailureResponse",
                                },
                            },
                        },
                    },
                },
            },
        },
    },
    "components": {
        "schemas": {
            "ProcessPaymentRequest": {
                "type": "object",
                "properties": {
                    "amount": {
                        "type": "number",
                        "multipleOf": 0.01,
                        "example": 100,
                    },
                    "currency": {
                        "type": "string",
                        "minLength": 3,
                        "maxLength": 3,
                        "example": "GHS",
                        "description": "ISO 4217 currency code (normalized to uppercase).",
                    },
                },
                "required": ["amount", "currency"],
            },
            "ProcessPaymentSuccess": {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean", "example": True},
                    "message": {"type": "string", "example": "Charged 100 GHS"},
                },
                "required": ["success", "message"],
            },
            "ValidationErrorResponse": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "example": "Validation failed"},
                    "errors": {"type": "string", "example": "...validation details..."},
                },
                "required": ["message", "errors"],
            },
            "IdempotencyHeaderErrorResponse": {
                "type": "object",
                "properties": {
                    "error": {"type": "string", "example": "Missing idempotency key"},
                    "message": {"type": "string", "example": "The Idempotency-Key header is required for POST requests"},
                },
                "required": ["error", "message"],
            },
            "IdempotencyConflictResponse": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "example": "Idempotency key already used for a different request body."},
                },
                "required": ["message"],
            },
            "ReplayFailureResponse": {
                "type": "object",
                "properties": {
                    "error": {"type": "string", "example": "Request could not be replayed"},
                    "message": {"type": "string", "example": "Original request did not complete successfully"},
                },
                "required": ["error", "message"],
            },
        },
    },
}
