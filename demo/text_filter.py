#!/usr/bin/env python3
"""Log file text filtering demo.

Demonstrates grep-style text filtering on log files.

Usage:
    ./setup.sh  # First, run setup to create data files
    python text_filter.py
"""

import time
import sys
import os

# Add parent directory to path for local development
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shellspark import Pipeline

print("=== Text Filtering Demo ===")
print("Task: Find all ERROR and WARN entries in application logs")
print()

# Show the source data
print("Source data (demo/data/app.log):")
print("-" * 70)
with open(os.path.join(os.path.dirname(__file__), "data/app.log")) as f:
    for i, line in enumerate(f):
        if i < 5:  # Show first 5 lines
            print(line.rstrip())
        elif i == 5:
            print("...")
            break
print()

# Filter for ERROR entries
print("=== ERROR entries ===")
start = time.time()

errors = (
    Pipeline("demo/data/app.log")
    .filter(line__contains="ERROR")
    .run()
)

for row in errors:
    print(row)

elapsed_errors = time.time() - start
print(f"\nFound {len(errors)} ERROR entries in {elapsed_errors:.3f}s")

# Filter for WARN entries
print()
print("=== WARN entries ===")
start = time.time()

warnings = (
    Pipeline("demo/data/app.log")
    .filter(line__contains="WARN")
    .run()
)

for row in warnings:
    print(row)

elapsed_warnings = time.time() - start
print(f"\nFound {len(warnings)} WARN entries in {elapsed_warnings:.3f}s")

# Combined filter using regex OR
print()
print("=== All issues (ERROR|WARN) ===")
start = time.time()

issues = (
    Pipeline("demo/data/app.log")
    .filter(line__regex="(ERROR|WARN)")
    .run()
)

for row in issues:
    print(row)

elapsed_combined = time.time() - start
print(f"\nFound {len(issues)} total issues in {elapsed_combined:.3f}s")
