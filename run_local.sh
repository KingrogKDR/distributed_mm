#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

# start server in background
python -u server.py --privacy --masks 8 &
SERVER_PID=$!
echo "server pid $SERVER_PID"
sleep 1

# start workers in background
python -u worker.py --id w1 &
W1=$!
python -u worker.py --id w2 &
W2=$!
python -u worker.py --id w3 &
W3=$!

# wait for server to finish (it will exit after aggregation)
wait $SERVER_PID

# give workers a moment, then stop them if still alive
sleep 1
kill $W1 $W2 $W3 2>/dev/null || true

echo "demo finished"
