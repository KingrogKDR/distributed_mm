# worker.py
import asyncio
import json
import logging
import argparse
import time
import random

import websockets
import common

logging.basicConfig(level=logging.INFO)

async def dot(vx, vy):
    s = 0
    for a,b in zip(vx, vy):
        s += int(a) * int(b)
    return s

async def run_worker(server_url: str, worker_id: str):
    try:
        async with websockets.connect(server_url) as ws:
            await ws.send(common.make_message(common.MSG_REGISTER, {"worker_id": worker_id}))
            logging.info("[%s] registered", worker_id)
            while True:
                # request task
                await ws.send(common.make_message(common.MSG_REQUEST))
                try:
                    raw = await ws.recv()
                except websockets.exceptions.ConnectionClosedOK:
                    logging.info("[%s] server closed connection (OK)", worker_id)
                    return
                except Exception as e:
                    logging.info("[%s] recv error: %s", worker_id, e)
                    await asyncio.sleep(0.5)
                    continue

                msg = json.loads(raw)
                typ = msg.get("type")
                if typ == common.MSG_TASK:
                    body = msg.get("body", {})
                    tid = body["task_id"]
                    vx = body["vector_x"]
                    vy = body["vector_y"]
                    logging.info("[%s] got task %s (len vectors: %d)", worker_id, tid, len(vx))
                    # quick compute
                    d = sum(int(a) * int(b) for a, b in zip(vx, vy))
                    res = {"task_id": tid, "dot": str(d)}
                    await ws.send(common.make_message(common.MSG_RESULT, res))
                    logging.info("[%s] sent result %s", worker_id, tid)
                elif typ == common.MSG_NO_TASK:
                    await asyncio.sleep(0.05)
                else:
                    logging.debug("[%s] unknown message %s", worker_id, msg)
    except websockets.exceptions.ConnectionClosedOK:
        logging.info("[%s] connection closed (server went away) — exiting", worker_id)
    except Exception as e:
        logging.exception("[%s] worker error: %s", worker_id, e)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", default="ws://localhost:8080")
    parser.add_argument("--id", default=f"worker-{int(time.time())}")
    args = parser.parse_args()
    url = args.server.rstrip("/") + "/ws"
    asyncio.run(run_worker(url, args.id))

if __name__ == "__main__":
    main()
