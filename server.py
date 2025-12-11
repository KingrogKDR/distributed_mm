from datetime import datetime, UTC

import asyncio
import json
import random
import logging
from typing import Dict, Any
import argparse
import time
from datetime import datetime
from pathlib import Path

import websockets

import common
import mask

# --- Styling (ANSI) ---
CSI = "\x1b["
COLOR_RESET = CSI + "0m"
COLOR_CYAN = CSI + "36m"
COLOR_GREEN = CSI + "32m"
COLOR_MAGENTA = CSI + "35m"

# --- Logging setup (clean timestamps) ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S"
)

def term(msg: str, color: str = ""):
    if color:
        return f"{color}{msg}{COLOR_RESET}"
    return msg

# Structured JSONL log file
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
SERVER_JSONL = LOG_DIR / "server.jsonl"

def write_server_json(obj: dict):
    try:
        with SERVER_JSONL.open("a", encoding="utf-8") as f:
            f.write(json.dumps(obj, default=str) + "\n")
    except Exception:
        logging.exception("failed to write server jsonl")

def iso_now():
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")

def log(msg: str):
    logging.info(term(f"[SERVER] {msg}", COLOR_CYAN))

# Example matrices (small demo). Replace with larger or generator as needed.
A = [
    [1, 2, 3],
    [4, 5, 6],
]
B = [
    [7, 8],
    [9, 10],
    [11, 12],
]

class Worker:
    def __init__(self, id: str, ws):
        self.id = id
        self.ws = ws

class Server:
    def __init__(self, host="localhost", port=8080, privacy=True, maskS=8, timeout=60):
        self.host = host
        self.port = port
        self.privacy = privacy
        self.maskS = maskS
        self.timeout = timeout

        self.rows = [list(map(int, row)) for row in A]
        # build columns of B
        k = len(self.rows[0])
        m = len(B[0])
        self.cols = []
        for j in range(m):
            col = [B[t][j] for t in range(k)]
            self.cols.append(col)

        self.task_queue: asyncio.Queue = asyncio.Queue()
        self.result_queue: asyncio.Queue = asyncio.Queue()

        self.workers: Dict[str, Worker] = {}
        self.state: Dict[str, Dict[str, int]] = {}
        self.masksA = []
        self.masksB = []
        self.offsets = []

        # for latency accounting
        self.sent_at: Dict[str, float] = {}  # task_id -> epoch seconds

    async def handler(self, ws):
        try:
            raw = await ws.recv()
        except Exception:
            return
        msg = common.parse_message(raw)
        if msg.get("type") != common.MSG_REGISTER:
            log(f"expected register, got {msg}")
            await ws.close()
            return
        reg = msg.get("body", {})
        wid = reg.get("worker_id", f"w-{time.time()}")
        worker = Worker(wid, ws)
        self.workers[wid] = worker
        log(term(f"worker {wid} registered", COLOR_GREEN))
        write_server_json({"ts": iso_now(), "event": "worker_registered", "worker_id": wid})

        try:
            while True:
                raw = await ws.recv()
                msg = common.parse_message(raw)
                typ = msg.get("type")
                if typ == common.MSG_REQUEST:
                    try:
                        t = self.task_queue.get_nowait()
                        task_id = t.get("task_id")
                        # record send time for latency
                        self.sent_at[task_id] = time.time()
                        log(term(f"→ task {task_id} → {wid}", COLOR_MAGENTA))
                        write_server_json({
                            "ts": iso_now(),
                            "event": "dispatch",
                            "task_id": task_id,
                            "worker_id": wid
                        })
                        await ws.send(common.make_message(common.MSG_TASK, t))
                    except asyncio.QueueEmpty:
                        await ws.send(common.make_message(common.MSG_NO_TASK))
                elif typ == common.MSG_RESULT:
                    body = msg.get("body", {})
                    task_id = body.get("task_id")
                    # compute latency if we dispatched it
                    now = time.time()
                    sent = self.sent_at.pop(task_id, None)
                    latency = None
                    if sent is not None:
                        latency = max(0.0, now - sent)
                    log(term(f"← result {task_id} ← {wid}", COLOR_MAGENTA))
                    write_server_json({
                        "ts": iso_now(),
                        "event": "result_received",
                        "task_id": task_id,
                        "worker_id": wid,
                        "latency_seconds": latency
                    })
                    await self.result_queue.put(body)
                else:
                    logging.debug(f"unknown msg from worker {wid}: {msg}")
        except Exception as e:
            log(term(f"worker {wid} disconnected: {e}", COLOR_CYAN))
            write_server_json({"ts": iso_now(), "event": "worker_disconnect", "worker_id": wid, "error": str(e)})
        finally:
            if wid in self.workers:
                del self.workers[wid]

    def setup_masks(self):
        if not self.privacy:
            return
        k = len(self.rows[0])
        S = self.maskS
        self.masksA = [mask.rand_vector(k, 32) for _ in range(S)]
        self.masksB = [mask.rand_vector(k, 32) for _ in range(S)]
        self.offsets = [[mask.dot(self.masksA[i], self.masksB[j]) for j in range(S)] for i in range(S)]

    async def generate_tasks(self):
        n = len(self.rows)
        m = len(self.cols)
        tasks = []
        if self.privacy:
            for i in range(n):
                for j in range(m):
                    ri = random.randrange(self.maskS)
                    rj = random.randrange(self.maskS)
                    x_plus = mask.add_vec(self.rows[i], self.masksA[ri])
                    y_plus = mask.add_vec(self.cols[j], self.masksB[rj])
                    x_minus = mask.sub_vec(self.rows[i], self.masksA[ri])
                    y_minus = mask.sub_vec(self.cols[j], self.masksB[rj])
                    tplus = {
                        "task_id": f"{i}_{j}_+_{ri}_{rj}",
                        "vector_x": [str(v) for v in x_plus],
                        "vector_y": [str(v) for v in y_plus],
                    }
                    tminus = {
                        "task_id": f"{i}_{j}_-_{ri}_{rj}",
                        "vector_x": [str(v) for v in x_minus],
                        "vector_y": [str(v) for v in y_minus],
                    }
                    # placeholder for reconstruction
                    self.state[f"{i}_{j}"] = {"plus": None, "minus": None}
                    tasks.append(tplus)
                    tasks.append(tminus)
        else:
            for i in range(n):
                for j in range(m):
                    t = {
                        "task_id": f"{i}_{j}",
                        "vector_x": [str(v) for v in self.rows[i]],
                        "vector_y": [str(v) for v in self.cols[j]],
                    }
                    tasks.append(t)

        random.shuffle(tasks)
        for t in tasks:
            await self.task_queue.put(t)
        log(term(f"pushed {len(tasks)} tasks", COLOR_CYAN))
        write_server_json({"ts": iso_now(), "event": "tasks_pushed", "count": len(tasks)})

    async def aggregate(self):
        n = len(self.rows)
        m = len(self.cols)
        C = [[0 for _ in range(m)] for __ in range(n)]
        pending = n * m
        start = time.time()
        per_task_latencies = []  # collect latencies for stats
        while pending > 0:
            try:
                body = await asyncio.wait_for(self.result_queue.get(), timeout=self.timeout)
            except asyncio.TimeoutError:
                log(term("aggregation timeout", COLOR_CYAN))
                write_server_json({"ts": iso_now(), "event": "aggregation_timeout"})
                break
            tid = body.get("task_id")
            dot = int(body.get("dot"))
            # compute latency if available in JSONL or server.sent_at (we logged earlier)
            # parse privacy id pattern
            parts = tid.split("_")
            if len(parts) >= 5 and (parts[2] == '+' or parts[2] == '-'):
                i = int(parts[0])
                j = int(parts[1])
                sign = parts[2]
                ri = int(parts[3])
                rj = int(parts[4])
                key = f"{i}_{j}"
                ps = self.state.get(key)
                if ps is None:
                    self.state[key] = {"plus": None, "minus": None}
                    ps = self.state[key]
                if sign == '+':
                    ps["plus"] = dot
                else:
                    ps["minus"] = dot
                if ps["plus"] is not None and ps["minus"] is not None:
                    offset = self.offsets[ri][rj]
                    Rij2 = ps["plus"] + ps["minus"] - 2 * offset
                    Rij = Rij2 // 2
                    C[i][j] = Rij
                    pending -= 1
                    del self.state[key]
            else:
                # plain task id "<i>_<j>"
                i, j = map(int, tid.split("_"))
                C[i][j] = dot
                pending -= 1

            # attempt to parse latency if present in server.jsonl (not necessary)
            # (server recorded latency at reception and wrote to JSONL already)
        elapsed = time.time() - start
        log(term(f"aggregation done in {elapsed:.3f}s", COLOR_GREEN))
        write_server_json({"ts": iso_now(), "event": "aggregation_done", "elapsed_seconds": elapsed, "matrix": C})

        log(term("C =", COLOR_CYAN))
        for row in C:
            row_s = " ".join(str(x) for x in row)
            log(f"[ {row_s} ]")
            # also write each row as structured line
            write_server_json({"ts": iso_now(), "event": "matrix_row", "row": row})

    async def serve(self):
        self.setup_masks()
        # start websocket server
        server = await websockets.serve(self.handler, self.host, self.port)
        log(term(f"Server listening on ws://{self.host}:{self.port}", COLOR_CYAN))
        write_server_json({"ts": iso_now(), "event": "server_start", "host": self.host, "port": self.port})

        # generate tasks
        await self.generate_tasks()

        # run aggregator until done
        await self.aggregate()

        # close server
        server.close()
        await server.wait_closed()
        write_server_json({"ts": iso_now(), "event": "server_stop"})

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", default=8080, type=int)
    parser.add_argument("--privacy", action="store_true")
    parser.add_argument("--masks", default=8, type=int)
    parser.add_argument("--timeout", default=60, type=int)
    args = parser.parse_args()

    srv = Server(host=args.host, port=args.port, privacy=args.privacy, maskS=args.masks, timeout=args.timeout)
    asyncio.run(srv.serve())

if __name__ == "__main__":
    main()
