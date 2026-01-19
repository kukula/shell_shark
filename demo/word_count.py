#!/usr/bin/env python3
"""Classic word count demo.

NOTE: This demo requires the `flatmap` feature which is not yet implemented.
This file shows the planned API for word counting.

When implemented, the pipeline will compile to:
    cat demo/data/book.txt | tr ' ' '\\n' | grep -E '^[a-zA-Z]+$' | \\
    sort | uniq -c | sort -rn | head -20

Usage:
    ./setup.sh  # First, run setup to download book.txt
    python word_count.py
"""

import os
import sys

print("=== Word Count Demo ===")
print("Task: Find the most frequent words in Pride and Prejudice")
print()

book_path = os.path.join(os.path.dirname(__file__), "data/book.txt")

# Show file info
if os.path.exists(book_path):
    size = os.path.getsize(book_path)
    with open(book_path) as f:
        lines = sum(1 for _ in f)
    print(f"Source: demo/data/book.txt ({size:,} bytes, {lines:,} lines)")
else:
    print("Error: demo/data/book.txt not found. Run ./setup.sh first.")
    sys.exit(1)

print()
print("NOTE: The `flatmap` feature required for word counting is not yet implemented.")
print()
print("Planned API:")
print("-" * 50)
print("""
from shellspark import Pipeline

result = (
    Pipeline("demo/data/book.txt")
    .flatmap(split=r"\\s+")           # Split on whitespace
    .filter(line__regex=r"^[a-zA-Z]+$")  # Only words
    .group_by("word")
    .agg(count=("*", "count"))
    .sort("count", desc=True)
    .limit(20)
    .run()
)
""")

print("This will compile to the shell pipeline:")
print("-" * 50)
print("""
cat demo/data/book.txt | \\
  tr ' ' '\\n' | \\
  grep -E '^[a-zA-Z]+$' | \\
  sort | uniq -c | sort -rn | head -20
""")

# Show what the raw shell command produces
print("Raw shell output (for reference):")
print("-" * 50)
import subprocess
result = subprocess.run(
    "cat demo/data/book.txt | tr ' ' '\\n' | grep -E '^[a-zA-Z]+$' | sort | uniq -c | sort -rn | head -20",
    shell=True,
    capture_output=True,
    text=True
)
print(result.stdout)
