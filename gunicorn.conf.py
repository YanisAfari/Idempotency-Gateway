"""
Gunicorn configuration for production deployment
"""

# Server socket
bind = "0.0.0.0:3000"

# Worker processes
workers = 1  # Single worker for in-memory idempotency store
worker_class = "sync"
threads = 4  # 4 threads per worker for concurrent request handling

# Logging
accesslog = "-"  # Log to stdout
errorlog = "-"   # Log to stderr
loglevel = "info"

# Process naming
proc_name = "idempotency-gateway"

# Server mechanics
timeout = 120  # 120 second timeout for long-running requests
keepalive = 5  # Keep connections alive for 5 seconds