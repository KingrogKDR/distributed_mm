from datetime import datetime, UTC


# worker.py
import asyncio
import json
import logging
import argparse
import time
from datetime import datetime
from pathlib import Path

import websockets
import common

# --- Styling (ANSI) ---
CSI = "\x1b["
COLOR_RESET = CSI + "0m"
COLOR_YELLOW = CSI + "33m"
COLOR_BLUE = CSI + "34m"

# clean timestamped logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S"
)

def iso_now():
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def term(msg: str, color: str = ""):
    if color:
        return f"{color}{msg}{COLOR_RESET}"
    return msg

# structured JSONL per worker
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

def write_worker_json(worker_id: str, obj: dict):
    p = LOG_DIR / f"worker-{worker_id}.jsonl"
    try:
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(obj, default=str) + "\n")
    except Exception:
        logging.exception("failed to write worker jsonl")

def logw(worker_id: str, msg: str):
    logging.info(term(f"[{worker_id}] {msg}", COLOR_YELLOW))

async def dot(vx, vy):
    s = 0
    for a, b in zip(vx, vy):
        s += int(a) * int(b)
    return s

async def run_worker(server_url: str, worker_id: str):
    url = server_url
    try:
        async with websockets.connect(url) as ws:
            # register
            await ws.send(common.make_message(common.MSG_REGISTER, {"worker_id": worker_id}))
            logw(worker_id, "registered")
            write_worker_json(worker_id, {"ts": iso_now(), "event": "registered", "worker_id": worker_id})
            while True:
                # request task
                await ws.send(common.make_message(common.MSG_REQUEST))
                try:
                    raw = await ws.recv()
                except websockets.exceptions.ConnectionClosedOK:
                    logw(worker_id, "server closed connection (OK)")
                    write_worker_json(worker_id, {"ts": iso_now(), "event": "connection_closed_ok"})
                    return
                except Exception as e:
                    logw(worker_id, f"recv error: {e}")
                    write_worker_json(worker_id, {"ts": iso_now(), "event": "recv_error", "error": str(e)})
                    await asyncio.sleep(0.5)
                    continue

                msg = json.loads(raw)
                typ = msg.get("type")
                if typ == common.MSG_TASK:
                    body = msg.get("body", {})
                    tid = body["task_id"]
                    vx = body["vector_x"]
                    vy = body["vector_y"]
                    logw(worker_id, term(f"← task {tid}", COLOR_BLUE))
                    # compute and measure compute time
                    t0 = time.time()
                    d = sum(int(a) * int(b) for a, b in zip(vx, vy))
                    compute_seconds = time.time() - t0
                    res = {"task_id": tid, "dot": str(d)}
                    await ws.send(common.make_message(common.MSG_RESULT, res))
                    logw(worker_id, term(f"→ result {tid}", COLOR_BLUE))
                    # structured JSON line
                    write_worker_json(worker_id, {
                        "ts": iso_now(),
                        "event": "task_done",
                        "task_id": tid,
                        "compute_seconds": compute_seconds
                    })
                elif typ == common.MSG_NO_TASK:
                    await asyncio.sleep(0.05)
                else:
                    logging.debug(f"[{worker_id}] unknown message {msg}")
    except websockets.exceptions.ConnectionClosedOK:
        logw(worker_id, "connection closed (server went away) — exiting")
        write_worker_json(worker_id, {"ts": iso_now(), "event": "closed_ok"})
    except Exception as e:
        logging.exception(f"[{worker_id}] worker error: {e}")
        write_worker_json(worker_id, {"ts": iso_now(), "event": "error", "error": str(e)})

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", default="ws://localhost:8080")
    parser.add_argument("--id", default=f"worker-{int(time.time())}")
    args = parser.parse_args()
    url = args.server.rstrip("/") + "/ws"
    asyncio.run(run_worker(url, args.id))

if __name__ == "__main__":
    main()
