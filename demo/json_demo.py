#!/usr/bin/env python3
"""JSON field extraction and filtering demo.

Demonstrates JSON parsing, field selection, and filtering.

Usage:
    ./setup.sh  # First, run setup to download users.json
    python json_demo.py
"""

import json
import time
import sys
import os

# Add parent directory to path for local development
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shellspark import Pipeline

print("=== JSON Demo ===")
print("Task: Extract and filter user data from JSONPlaceholder API")
print()

json_path = os.path.join(os.path.dirname(__file__), "data/users.json")

# Show source data preview
if os.path.exists(json_path):
    with open(json_path) as f:
        lines = f.readlines()
    print(f"Source: demo/data/users.json ({len(lines)} users, NDJSON format)")
    print()
    print("Sample record (first line):")
    print("-" * 50)
    sample = json.loads(lines[0])
    print(json.dumps(sample, indent=2)[:400] + "...")
else:
    print("Error: demo/data/users.json not found. Run ./setup.sh first.")
    sys.exit(1)

print()

# Example 1: Select specific fields
print("=== Example 1: Select name and email ===")
start = time.time()

result = (
    Pipeline("demo/data/users.json")
    .parse("json")
    .select("name", "email")
    .run()
)

for row in result:
    # Result may be string (TSV) or dict depending on output format
    if isinstance(row, dict):
        print(f"  {row.get('name', 'N/A')}: {row.get('email', 'N/A')}")
    else:
        print(f"  {row}")

elapsed = time.time() - start
print(f"\nCompleted in {elapsed:.3f}s")

# Example 2: Select with website
print()
print("=== Example 2: User websites ===")
start = time.time()

result = (
    Pipeline("demo/data/users.json")
    .parse("json")
    .select("name", "website")
    .run()
)

print(f"{'Name':<25} {'Website':<30}")
print("-" * 55)
for row in result:
    if isinstance(row, dict):
        print(f"{row.get('name', 'N/A'):<25} {row.get('website', 'N/A'):<30}")
    else:
        # Handle TSV output
        parts = str(row).split('\t') if '\t' in str(row) else [str(row)]
        if len(parts) >= 2:
            print(f"{parts[0]:<25} {parts[1]:<30}")
        else:
            print(f"  {row}")

elapsed = time.time() - start
print(f"\nCompleted in {elapsed:.3f}s")
