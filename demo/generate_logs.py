#!/usr/bin/env python3
"""Generate realistic JSON web server logs for benchmarking."""

import json
import random
import sys

PATHS = [
    "/api/users", "/api/users/{id}", "/api/orders", "/api/orders/{id}",
    "/api/products", "/api/products/{id}", "/api/auth/login", "/api/auth/logout",
    "/api/cart", "/api/checkout", "/health", "/metrics"
]

STATUS_WEIGHTS = {
    200: 70, 201: 10, 204: 5,   # Success
    400: 5, 401: 3, 403: 2, 404: 8, 422: 2,  # Client errors
    500: 3, 502: 1, 503: 1      # Server errors
}

METHODS = ["GET", "POST", "PUT", "DELETE"]
METHOD_WEIGHTS = [60, 20, 15, 5]


def generate_log():
    status = random.choices(list(STATUS_WEIGHTS.keys()), list(STATUS_WEIGHTS.values()))[0]
    # Errors tend to be slower
    base_time = 500 if status >= 400 else 100
    return {
        "timestamp": 1704067200 + random.randint(0, 86400 * 7),  # 1 week of logs
        "method": random.choices(METHODS, METHOD_WEIGHTS)[0],
        "path": random.choice(PATHS),
        "status": status,
        "ip": f"10.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}",
        "response_time": max(1, int(random.gauss(base_time, base_time * 0.5))),
        "user_agent": random.choice(["Mozilla/5.0", "curl/7.68", "python-requests/2.28", "PostmanRuntime/7.29"]),
        "request_id": f"{random.randint(100000, 999999):06x}"
    }


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5_000_000
    for _ in range(n):
        print(json.dumps(generate_log()))
