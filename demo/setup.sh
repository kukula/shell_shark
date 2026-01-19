#!/bin/bash
# Setup script for ShellSpark demos
# Downloads sample data files and generates test data

set -e

cd "$(dirname "$0")"

echo "=== ShellSpark Demo Setup ==="
echo ""

# Create data directory
mkdir -p data

# Download Pride and Prejudice from Project Gutenberg
echo "Downloading book.txt (Pride and Prejudice)..."
curl -sL "https://www.gutenberg.org/cache/epub/1342/pg1342.txt" -o data/book.txt
echo "  -> data/book.txt ($(wc -c < data/book.txt | tr -d ' ') bytes)"

# Download users.json from JSONPlaceholder (convert array to NDJSON)
echo "Downloading users.json..."
curl -sL "https://jsonplaceholder.typicode.com/users" | jq -c '.[]' > data/users.json
echo "  -> data/users.json ($(wc -l < data/users.json | tr -d ' ') records, NDJSON format)"

# Generate sales.csv sample data
echo "Generating sales.csv..."
cat > data/sales.csv << 'EOF'
date,region,category,quantity,price
2024-01-15,North,Electronics,5,299.99
2024-01-15,South,Clothing,12,49.99
2024-01-16,East,Electronics,3,599.99
2024-01-16,West,Home,8,79.99
2024-01-17,North,Clothing,15,29.99
2024-01-17,South,Electronics,2,999.99
2024-01-18,East,Home,20,24.99
2024-01-18,West,Clothing,7,89.99
2024-01-19,North,Home,10,149.99
2024-01-19,South,Home,6,199.99
2024-01-20,East,Clothing,25,39.99
2024-01-20,West,Electronics,1,1499.99
2024-01-21,North,Electronics,4,449.99
2024-01-21,South,Clothing,18,59.99
2024-01-22,East,Home,12,89.99
2024-01-22,West,Home,3,299.99
2024-01-23,North,Clothing,8,69.99
2024-01-23,South,Electronics,6,349.99
2024-01-24,East,Electronics,2,799.99
2024-01-24,West,Clothing,14,44.99
EOF
echo "  -> data/sales.csv (20 records)"

# Generate app.log sample data
echo "Generating app.log..."
cat > data/app.log << 'EOF'
2024-01-15 08:00:01 INFO  [main] Application started successfully
2024-01-15 08:00:02 DEBUG [db] Connection pool initialized with 10 connections
2024-01-15 08:00:15 INFO  [http] Request GET /api/users completed in 45ms
2024-01-15 08:01:23 WARN  [auth] Failed login attempt for user: admin
2024-01-15 08:02:45 ERROR [db] Connection timeout after 30000ms
2024-01-15 08:02:46 INFO  [db] Retrying connection...
2024-01-15 08:02:47 INFO  [db] Connection restored
2024-01-15 08:05:12 INFO  [http] Request POST /api/orders completed in 120ms
2024-01-15 08:07:33 WARN  [cache] Cache miss for key: user_profile_123
2024-01-15 08:10:01 ERROR [payment] Payment gateway returned error: insufficient_funds
2024-01-15 08:10:02 INFO  [payment] Notifying user about payment failure
2024-01-15 08:15:44 DEBUG [scheduler] Running scheduled task: cleanup_sessions
2024-01-15 08:20:00 INFO  [http] Request GET /api/products completed in 32ms
2024-01-15 08:25:18 WARN  [auth] Token expired for session: abc123
2024-01-15 08:30:55 ERROR [validation] Invalid input: email format incorrect
2024-01-15 08:35:22 INFO  [http] Request PUT /api/users/456 completed in 89ms
2024-01-15 08:40:11 DEBUG [cache] Cache hit for key: product_catalog
2024-01-15 08:45:33 INFO  [metrics] System health check passed
2024-01-15 08:50:47 WARN  [disk] Disk usage at 85%
2024-01-15 08:55:00 ERROR [network] DNS resolution failed for external-api.example.com
EOF
echo "  -> data/app.log (20 entries)"

# Generate test logs for web log analysis demo
echo "Generating web logs (100,000 records)..."
cd ..
python demo/generate_logs.py 100000 > demo/data/logs.json
# Also create data/logs/ at project root for shellspark_demo.py compatibility
mkdir -p data/logs
cp demo/data/logs.json data/logs/test.json
cd demo
echo "  -> demo/data/logs.json (100,000 records)"
echo "  -> data/logs/test.json (copy for shellspark_demo.py)"

echo ""
echo "=== Setup complete! ==="
echo ""
echo "Data files created in demo/data/:"
ls -la data/
echo ""
echo "Run the demos:"
echo "  python csv_aggregation.py"
echo "  python text_filter.py"
echo "  python word_count.py"
echo "  python json_demo.py"
echo "  python shellspark_demo.py"
