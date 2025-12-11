#!/usr/bin/env bash
set -e
python -u server.py --privacy --masks 8 &
SERVER_PID=$!
sleep 1
python -u worker.py --id w1 &
python -u worker.py --id w2 &
python -u worker.py --id w3 &
# wait for server to print results
sleep 6
kill $SERVER_PID || true
echo "test completed"
