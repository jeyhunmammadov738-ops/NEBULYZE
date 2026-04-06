import pybreaker
import os

# Create a circuit breaker for Redis
redis_breaker = pybreaker.CircuitBreaker(
    fail_max=5,  # Allow 5 failures before opening
    reset_timeout=60,  # Reset after 60 seconds
    exclude=[KeyboardInterrupt]  # Don't count KeyboardInterrupt as failure
)

# Create a circuit breaker for database
db_breaker = pybreaker.CircuitBreaker(
    fail_max=3,
    reset_timeout=30,
    exclude=[KeyboardInterrupt]
)

# Create a circuit breaker for external APIs (yt-dlp)
external_api_breaker = pybreaker.CircuitBreaker(
    fail_max=3,
    reset_timeout=60,
    exclude=[KeyboardInterrupt]
)