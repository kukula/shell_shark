#!/bin/bash
# Full benchmark script for ShellSpark
set -e

cd "$(dirname "$0")/.."

echo "=== Generating test data ==="
mkdir -p data/logs
python demo/generate_logs.py 5000000 > data/logs/access.json
cd data/logs && split -l 500000 access.json log_ && rm access.json
for f in log_*; do mv "$f" "$f.json"; done
cd ../..

echo ""
echo "=== Data stats ==="
echo "Files: $(ls data/logs/*.json | wc -l)"
echo "Size: $(du -sh data/logs | cut -f1)"
echo "Lines: $(cat data/logs/*.json | wc -l)"

echo ""
echo "=== ShellSpark benchmark ==="
time python demo/shellspark_demo.py

echo ""
echo "=== Raw shell pipeline benchmark ==="
time (
find data/logs -name '*.json' -print0 \
| xargs -0 -P8 jq -r 'select(.status >= 400) | [.path, .ip, .response_time] | @tsv' \
| awk -F'\t' '
  {
    errors[$1]++
    times[$1] += $3
    ips[$1, $2] = 1
  }
  END {
    for (path in errors) {
      uips = 0
      for (key in ips) {
        split(key, parts, SUBSEP)
        if (parts[1] == path) uips++
      }
      printf "%s\t%d\t%d\t%.1f\n", path, errors[path], uips, times[path]/errors[path]
    }
  }
' \
| sort -t$'\t' -k2 -rn \
| head -20
)

echo ""
echo "=== Done ==="
