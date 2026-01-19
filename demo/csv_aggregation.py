#!/usr/bin/env python3
"""CSV sales data aggregation demo.

Demonstrates CSV parsing, filtering, group_by, and aggregations.

Usage:
    ./setup.sh  # First, run setup to create data files
    python csv_aggregation.py
"""

import time
import sys
import os

# Add parent directory to path for local development
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shellspark import Pipeline

print("=== CSV Aggregation Demo ===")
print("Task: Calculate total revenue by region from sales data")
print()

# Show the source data
print("Source data (demo/data/sales.csv):")
print("-" * 50)
with open(os.path.join(os.path.dirname(__file__), "data/sales.csv")) as f:
    for i, line in enumerate(f):
        if i < 6:  # Show header + first 5 rows
            print(line.rstrip())
        elif i == 6:
            print("...")
            break
print()

start = time.time()

result = (
    Pipeline("demo/data/sales.csv")
    .parse("csv", header=True)
    .filter(quantity__gt=0)
    .group_by("region")
    .agg(
        total_orders=("*", "count"),
        total_quantity=("quantity", "sum"),
        total_revenue=("price * quantity", "sum")
    )
    .sort("total_revenue", desc=True)
    .run()
)

elapsed = time.time() - start

print("Results (revenue by region):")
print("-" * 50)
print(f"{'Region':<12} {'Orders':>8} {'Quantity':>10} {'Revenue':>12}")
print("-" * 50)
for row in result:
    print(f"{row['region']:<12} {row['total_orders']:>8} {row['total_quantity']:>10} ${row['total_revenue']:>11.2f}")

print()
print(f"Completed in {elapsed:.3f} seconds")
