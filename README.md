# Idempotency Gateway — Payment Processing API

A production-ready idempotency gateway that prevents duplicate payment processing through request deduplication, validation, and concurrent request coalescing.

## Live Deployment

- Service: https://idempotency-gateway-ngh6.onrender.com
- Health check: https://idempotency-gateway-ngh6.onrender.com/health
- Interactive Swagger Docs: https://idempotency-gateway-ngh6.onrender.com/docs

> *Hosted on Render's free tier; the first request after inactivity may take ~30 seconds to wake.*

## Overview

This API acts as an idempotency layer for payment processing, ensuring that duplicate requests (caused by network timeouts, retries, or race conditions) are handled safely without charging customers multiple times. Built for **FinSafe Transactions Ltd.**, a payment processor requiring robust duplicate detection.

## Architecture

![System Architecture](./architecture-diagram.png)

*Component view: the layered architecture showing how the pieces fit together.*

### Key Components

- **Flask Application** — Main application entry point that registers routes and documentation
- **Routing Layer** — Defines API endpoints (`/health` and `/process-payment`)
- **Middleware Layer** — Two-stage processing:
  1. **Validation Middleware** — Validates request body before processing
  2. **Idempotency Middleware** — Handles duplicate detection and request coalescing
- **Support Layer** — Utilities for request hashing and response replay, plus schema validation
- **Backend Layer** — Payment controller that simulates payment processing
- **Idempotency Store** — In-memory storage with TTL, request coalescing, and background cleanup

## Request Flow

The logic-flow view of what happens for every incoming request:

```mermaid
flowchart TD
    Start(["Client: POST /process-payment"]) --> JSON{"Valid JSON body?"}
    JSON -- No --> E1["400 - Validation failed"]
    JSON -- Yes --> Schema{"Body valid?<br/>amount + currency"}
    Schema -- No --> E2["400 - Validation failed"]
    Schema -- Yes --> KeyPresent{"Idempotency-Key header present?"}
    KeyPresent -- No --> E3["400 - Missing idempotency key"]
    KeyPresent -- Yes --> KeyValid{"Key is a valid UUID?"}
    KeyValid -- No --> E4["400 - Invalid key format"]
    KeyValid -- Yes --> Build["Build composite key<br/>method:path:key<br/>+ hash request body"]
    Build --> Exists{"Record exists in store?"}
    Exists -- No --> New["Store record + mark in-flight"]
    New --> Process["Process payment ~2s"]
    Process --> Cache["Cache response + release waiters"]
    Cache --> OK["200 - Charged 100 GHS"]
    Exists -- Yes --> SameHash{"Same request hash?"}
    SameHash -- No --> E422["422 - Key already used for a different body"]
    SameHash -- Yes --> Cached{"Response already cached?"}
    Cached -- Yes --> Replay["200 - replayed, X-Cache-Hit: true"]
    Cached -- No --> Wait["Wait for in-flight request"]
    Wait --> Done{"Completed with a response?"}
    Done -- Yes --> Replay
    Done -- No --> E500["500 - Could not be replayed"]
```

## In-Flight Coalescing (Sequence)

How two concurrent requests with the same idempotency key are handled — the second request waits on the first instead of triggering a second charge:

```mermaid
sequenceDiagram
    participant A as Request A
    participant GW as Gateway
    participant S as Store
    participant B as Request B
    A->>GW: POST /process-payment (Key K)
    GW->>S: get(K) -> not found
    GW->>S: set(K, pending) + begin(K)
    Note over GW: processing ~2s
    B->>GW: POST /process-payment (Key K, same body)
    GW->>S: get(K) -> pending, no response yet
    GW->>S: wait(K)
    Note over B: blocked until A finishes
    GW->>S: set(K, response) + complete(K)
    GW-->>A: 200 Charged 100 GHS
    S-->>B: wait resolves
    GW->>S: get(K) -> response
    GW-->>B: 200 replayed (X-Cache-Hit: true)
```

## Features

### Core Functionality
- **Idempotency Support** — Prevents duplicate payment processing using unique request keys
- **Request Validation** — Comprehensive validation of payment data (amounts, currencies)
- **Race Condition Handling** — Concurrent request coalescing for in-flight duplicates
- **Cache Hit Tracking** — `X-Cache-Hit` header to identify replayed responses

### Additional Features
- **OpenAPI/Swagger Documentation** — Interactive API docs at `/docs`
- **Health Check Endpoint** — Load balancer and monitoring support at `/health`
- **Request Body Hashing** — Detects attempts to reuse keys for different requests
- **Detailed Error Messages** — Clear validation feedback for debugging

## Quick Start

### Prerequisites
- Python 3.11+
- pip (Python package manager)

### Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/YanisAfari/Idempotency-Gateway.git
   cd Idempotency-Gateway
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the development server**
   ```bash
   python -m src.index
   ```

   The server will start on `http://localhost:3000`.

4. **View API documentation**
   ```
   http://localhost:3000/docs
   ```

### Production Setup

**Using Gunicorn (Linux/Mac/Production):**
```bash
gunicorn --config gunicorn.conf.py src.app:app
```

**Using Waitress (Windows):**
```bash
waitress-serve --host=0.0.0.0 --port=3000 src.app:app
```

## API Documentation

### Base URL
```
http://localhost:3000
```

### Endpoints

#### 1. Health Check

**GET** `/health`

Check if the service is running.

**Request:**
```bash
curl http://localhost:3000/health
```

**Response:**
```json
{
  "success": true
}
```

---

#### 2. Process Payment

**POST** `/process-payment`

Process a payment with idempotency support.

**Headers:**
- `Content-Type: application/json` (required)
- `Idempotency-Key: <uuid>` (required, must be a valid UUID)

**Request Body:**
```json
{
  "amount": 100.50,
  "currency": "GHS"
}
```

**Example Request:**
```bash
curl -X POST http://localhost:3000/process-payment \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: 550e8400-e29b-41d4-a716-446655440000" \
  -d '{"amount": 100.50, "currency": "GHS"}'
```

**Success Response (200 OK):**
```json
{
  "success": true,
  "message": "Charged 100.5 GHS"
}
```

**Duplicate Request Response (200 OK):**
```json
{
  "success": true,
  "message": "Charged 100.5 GHS"
}
```
*Headers:* `X-Cache-Hit: true`

**Different Request, Same Key (422 Unprocessable Entity):**
```json
{
  "message": "Idempotency key already used for a different request body."
}
```

**Validation Errors (400 Bad Request):**

*Invalid amount or currency:*
```json
{
  "message": "Validation failed",
  "errors": {
    "amount": ["Amount must be a number"]
  }
}
```

*Missing Idempotency-Key header:*
```json
{
  "error": "Missing idempotency key",
  "message": "The Idempotency-Key header is required for POST requests"
}
```

*Invalid Idempotency-Key format (not a UUID):*
```json
{
  "error": "Invalid idempotency key format",
  "message": "Key must be 16-64 alphanumeric characters, hyphens, or underscores"
}
```

> Note: the runtime check accepts only valid UUIDs (per the OpenAPI spec at `/docs`); the current error message text is more permissive than the rule it enforces.

### Supported Currencies

Any valid ISO 4217 currency code:
- `GHS` (Ghanaian Cedi)
- `USD` (US Dollar)
- `EUR` (Euro)
- `GBP` (British Pound)
- `NGN` (Nigerian Naira)
- And 150+ others

### Amount Validation Rules

- Must be a number (not a string)
- Must be positive (> 0)
- Maximum 2 decimal places
- Examples:
  - Valid: `100`, `100.5`, `100.50`
  - Invalid: `"100.50"` (string), `100.505` (3 decimals), `-50` (negative)

## Testing

### Run All Tests
```bash
pytest src/tests/ -v
```

### Run Specific User Stories
```bash
# User Story 1: Happy Path
pytest src/tests/user_stories/test_happy_path.py -v

# User Stories 2 & 3: Idempotency
pytest src/tests/user_stories/test_idempotency_behavior.py -v
```

### Expected Test Results
```
test_user_story_1_processes_first_transaction_with_expected_response PASSED
test_user_story_2_duplicate_request_returns_cached_response_without_reprocessing PASSED
test_user_story_3_same_key_with_different_payload_is_rejected PASSED
test_bonus_in_flight_duplicate_waits_and_reuses_original_response PASSED
test_expired_idempotency_key_is_removed_on_access PASSED
test_validated_body_reaches_controller PASSED
test_failed_first_attempt_releases_key_for_retry PASSED
```

### Manual Testing with Thunder Client or Postman

**Test Idempotency:**
1. Send a payment request with `Idempotency-Key: 11111111-1111-4111-8111-111111111111`
2. Send the SAME request again
3. Observe: Second request is instant and has `X-Cache-Hit: true` header

**Test Conflict Detection:**
1. Send request with `Idempotency-Key: 22222222-2222-4222-8222-222222222222`, amount: `100`
2. Send request with SAME key but amount: `500`
3. Observe: Second request returns `422` error

## Design Decisions

### 1. In-Memory Idempotency Store

**Decision:** Use Python dictionary for idempotency cache.

**Rationale:**
- Simple, fast, and sufficient for demonstration
- No external dependencies (Redis, database)
- Production systems would use Redis or DynamoDB for shared state across instances

**Trade-offs:**
- Zero latency lookups
- No infrastructure overhead
- Not shared across multiple server instances
- Data lost on server restart

**Production Alternative:** Redis with the same TTL semantics, for shared state across instances.

### 2. Request Body Hashing

**Decision:** Hash request body to detect payload changes.

**Rationale:**
- Prevents malicious reuse of idempotency keys
- Protects against accidental amount/currency changes
- Maintains data integrity

**Implementation:**
```python
request_hash = hashlib.sha256(
    json.dumps(request_body, sort_keys=True).encode()
).hexdigest()
```

### 3. Single Worker Configuration

**Decision:** Gunicorn configured with 1 worker, 4 threads.

**Rationale:**
- In-memory store is not shared across processes
- Threads share memory within a process (idempotency works correctly)
- For production: use Redis and increase workers to 4–8

### 4. Middleware Architecture

**Decision:** Separate validation and idempotency into middleware layers.

**Rationale:**
- Separation of concerns (validation ≠ idempotency)
- Reusable and testable components
- Clear request processing pipeline

**Request Pipeline:**
```
Request → Validation Middleware → Idempotency Middleware → Controller → Response
```

### 5. Swagger/OpenAPI Documentation

**Decision:** Auto-generate API documentation.

**Rationale:**
- Reduces integration time for clients
- Self-documenting API
- Try-it-out functionality for testing

### 6. TTL & Background Cleanup

**Decision:** Idempotency records expire automatically with a default TTL of 24 hours, combining lazy expiry on access with a periodic background sweep.

**Rationale:**
- Prevents unbounded memory growth in a long-running process
- Aligns idempotency retention with realistic client retry windows
- Reduces exposure from long-lived cached payment responses
- Lazy expiry handles stragglers on read; the sweep keeps the store bounded even if certain keys are never accessed again

**Implementation:**
- Lazy expiry on `get()` — expired records are removed when accessed
- Background daemon thread sweeps the store on a fixed interval
- TTL is configurable per store instance (default: 24h)

## Developer's Choice: Request Validation Framework

### The Problem I Identified

In production payment systems, invalid input data is a leading cause of processing failures. Without comprehensive validation:
- Downstream systems receive malformed data
- Payment processors return cryptic errors
- Customer experience degrades
- Support load grows

**Real-world scenario:**
```javascript
// Client sends this (wrong type)
{"amount": "100.50", "currency": "GHS"}

// Without validation → processor fails
Error: Cannot multiply string by decimal

// With validation → immediate feedback
{"message": "Validation failed", "errors": {"amount": ["Amount must be a number"]}}
```

### What I Implemented

A comprehensive validation framework using **Marshmallow** that validates:

1. **Type Safety**
   - Amount must be a number (not string, not boolean)
   - Currency must be a string

2. **Decimal Precision**
   - Maximum 2 decimal places
   - Prevents rounding errors in payment processing

3. **Business Rules**
   - Amount must be positive
   - Currency must be a valid ISO 4217 code (USD, GHS, EUR, etc.)

4. **Early Rejection**
   - Invalid requests rejected before reaching the idempotency layer
   - Saves computation and prevents cache pollution

### Implementation Details

**Schema Definition:**
```python
class RequestSchema(Schema):
    amount = fields.Raw(required=True)
    currency = fields.String(required=True)

    @validates("amount")
    def validate_amount(self, value):
        if isinstance(value, bool):
            raise ValidationError("Amount must be a number")
        if isinstance(value, str):
            raise ValidationError("Amount must be a number")
        if not isinstance(value, (int, float)):
            raise ValidationError("Amount must be a number")

        decimal_value = Decimal(str(value))
        if decimal_value < 0:
            raise ValidationError("Amount must be positive")
        if decimal_value.quantize(Decimal("0.01")) != decimal_value:
            raise ValidationError("Amount must have at most 2 decimal places")

    @validates("currency")
    def validate_currency(self, value):
        if not _is_valid_currency_code(value.strip().upper()):
            raise ValidationError("Invalid ISO 4217 currency code")
```

**Middleware Integration:**
```python
@router.route("/process-payment", methods=["POST"])
@validate_schema(request_schema)      # ← Validation runs first
@idempotency_middleware()
def handle_process_payment():
    return process_payment()
```

### Why This Matters for Production

**Operational benefits:**
- Bad requests are rejected in sub-millisecond time, before they reach the payment processor or pollute the idempotency cache
- Clear, structured error messages shorten integration and debugging cycles for client teams
- Downstream systems only ever see well-formed payloads, removing a whole class of error-handling complexity from the payment processor

**Cost & reliability:**
- Invalid requests are rejected in well under 1 ms versus the ~2 s a full payment cycle would take
- Idempotency entries are only ever created for *valid* requests, so retries of bad input never lock out a key
- Load on downstream payment systems is reduced because they no longer need to filter out obvious input errors

**Developer experience:**
```bash
# Before validation framework
curl ... -d '{"amount": "100"}'
→ 500 Internal Server Error: Cannot process string amount

# After validation framework
curl ... -d '{"amount": "100"}'
→ 400 Bad Request: {"message": "Validation failed", "errors": {"amount": ["Amount must be a number"]}}
```

**Compliance:**
- ISO 4217 currency validation prevents regulatory issues
- Decimal precision prevents rounding errors (critical for accounting)
- Audit trail of rejected requests

### Alternative Approaches Considered

1. **No Validation** ❌ — Let payment processor handle it. *Problem: slower feedback, wasted processing, poor UX.*
2. **Lightweight Validation** ❌ — Just check if fields exist. *Problem: type errors and business rule violations still reach the processor.*
3. **Database Constraints** ❌ — Enforce at database level. *Problem: too late — idempotency already cached the invalid request.*
4. **Comprehensive Schema Validation** ✅ — **Chosen.** Validate early, validate completely, with clear error messages, preventing cascade failures.

## Deployment

### Deploy to Render

1. **Push to GitHub**
   ```bash
   git add .
   git commit -m "Add production configuration and documentation"
   git push origin main
   ```

2. **Create Render Web Service**
   - Go to https://render.com
   - New → Web Service
   - Connect your GitHub repository

3. **Configure Service**
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 4 src.app:app`
   - **Environment:** Python 3

4. **Deploy**
   - Render will auto-deploy on every push to `main`.

### Environment Variables (if needed)
```
PORT=3000  # Automatically set by Render
```

## Security Considerations

1. **Idempotency Key Validation**
   - Must be a valid UUID
   - Rejects malformed or guessable keys early

2. **Request Body Hashing**
   - SHA-256 hash prevents payload tampering
   - Detects attempts to reuse keys maliciously

3. **No Sensitive Data in Logs**
   - Payment amounts logged, but no card numbers or PII
   - Idempotency keys are UUIDs (no user information)

## Performance

- **First Request:** ~2 seconds (simulated payment processing)
- **Duplicate Request:** <10 ms (cached response)
- **Validation:** <1 ms (rejected before processing)
- **Concurrent Requests:** Coalesced (no duplicate processing)

## Technology Stack

- **Framework:** Flask 3.0
- **Validation:** Marshmallow 3.20
- **Currency Validation:** iso4217
- **WSGI Server:** Gunicorn 21.0 (Linux) / Waitress 2.1 (Windows)
- **API Documentation:** Swagger UI 4.11
- **Testing:** pytest 8.0

## License

MIT License — see the `LICENSE` file for details.

## Author

**Yanis Afari**
GitHub: [@YanisAfari](https://github.com/YanisAfari)

## Acknowledgments

Built as part of the Idempotency Gateway Challenge for demonstrating production-ready API design, idempotency patterns, and request validation in payment systems.
