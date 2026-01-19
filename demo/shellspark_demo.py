#!/usr/bin/env python3
"""ShellSpark implementation of web log analysis.

Usage:
    python shellspark_demo.py
"""

import time
import sys
import os

# Add parent directory to path for local development
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shellspark import Pipeline

print("Starting ShellSpark analysis...")
start = time.time()

result = (
    Pipeline("data/logs/*.json")
    .parse("json")
    .filter(status__gte=400)
    .group_by("path")
    .agg(
        errors=("*", "count"),
        unique_ips=("ip", "countdistinct"),
        avg_response_time=("response_time", "mean")
    )
    .sort("errors", desc=True)
    .limit(20)
    .run()
)

elapsed = time.time() - start
print(f"\nCompleted in {elapsed:.2f} seconds\n")

# Display results
print(f"{'Path':<30} {'Errors':>10} {'Unique IPs':>12} {'Avg Time (ms)':>15}")
print("-" * 70)
for row in result:
    print(f"{row['path']:<30} {row['errors']:>10} {row['unique_ips']:>12} {row['avg_response_time']:>15.1f}")
