# Distributed Matrix Multiplication (Python)

A lightweight **distributed matrix multiplication system** implemented in **Python**, using:

- **asyncio**
- **websockets**
- **Beaver-style masking** (optional privacy mode)
- **worker-based parallel computation**

This project demonstrates how to distribute dot-product tasks across multiple workers, reconstruct the final result matrix, and optionally hide all matrix entries from workers via randomized masking.

---

## ✨ Features

### 🚀 Distributed Task Execution

- The server decomposes matrix multiplication into independent **dot-product tasks**.
- Workers fetch tasks, compute results, and return them.

### 🔐 Privacy-Preserving Computation (optional)

When `--privacy` is enabled:

- Each dot product is split into **two masked tasks** (+ and – shares).
- Workers only see masked vectors, never raw matrix data.
- Server reconstructs the true result using Beaver-style offsets.

### 🧩 Modular Architecture

- `server.py` — master orchestrator (task generation, result aggregation)
- `worker.py` — stateless workers that compute dot products
- `mask.py` — random masks, vector ops, dot products
- `common.py` — message types + helpers
- `run_local.sh` — runs server + 3 workers
- `test.sh` — simple test script

### 🐍 Python-native

- Uses Python’s built-in arbitrary-precision integers
- No external math libraries
- Pure WebSocket communication via `websockets` package

---

## 📦 Installation

```bash
git clone <your-repo-url>
cd distributed_mm
```

### 1️⃣ Create a Virtual Environment (recommended)

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2️⃣ Install Dependencies

```bash
pip install -r requirements.txt
```

---

## ▶️ Running the Distributed System

### Option A — Local demo (1 server + 3 workers)

```bash
./run_local.sh
```

You will see log output similar to:

```
Server listening on ws://localhost:8080
pushed 8 tasks
worker registered: w1
worker registered: w2
worker registered: w3
Aggregation done in X.XXs
Result C:
58 64
139 154
```

### Option B — Start server & workers manually

#### Start server:

```bash
python3 server.py --privacy --masks 8
```

#### Start workers (in 3 separate terminals):

```bash
python3 worker.py --id w1
python3 worker.py --id w2
python3 worker.py --id w3
```

---

## ⚙️ How It Works

### 1. Matrix Decomposition

Given matrices **A** (n × k) and **B** (k × m):
The server extracts:

- row vectors from A
- column vectors from B

Each dot-product `C[i][j] = dot(A[i], B[j])` becomes a task.

---

### 2. Privacy Mode (Beaver Masking)

When enabled:

- Server generates random mask vectors `a_mask` and `b_mask`
- For each dot-product `(i,j)` it creates:

  - **plus** share: `(A[i] + a_mask[r1]) ⋅ (B[j] + b_mask[r2])`
  - **minus** share: `(A[i] – a_mask[r1]) ⋅ (B[j] – b_mask[r2])`

Workers compute only masked dot products.

Server reconstructs the true dot-product:

```
R = (plus + minus − 2 * offset) / 2
```

Where `offset = dot(a_mask[r1], b_mask[r2])`.

---

### 3. Task Dispatching

Workers loop:

```
request_task → receive task → compute → send result → repeat
```

No worker holds state.

---

### 4. Result Aggregation

Once both shares for each `(i,j)` arrive, server reconstructs `C[i][j]`, prints matrix, and shuts down.

---

## 🧪 Testing

Run:

```bash
./test.sh
```

This:

- launches the server and workers via `python3`
- waits for aggregation
- prints results

---

## 📁 Project Structure

```
distributed_mm/
├── server.py          # Coordinating server
├── worker.py          # Worker node
├── mask.py            # Masking + vector arithmetic utils
├── common.py          # Message types, encoders, decoders
├── requirements.txt   # Python dependencies
├── run_local.sh       # Demo script (1 server + 3 workers)
└── test.sh            # Simple test runner
```

---

## 🛠️ Useful Commands

### Reinstall dependencies

```bash
pip install -r requirements.txt --upgrade
```

### Start a single worker for debugging

```bash
python3 worker.py --id debug-worker
```

### Increase mask strength

```bash
python3 server.py --privacy --masks 32
```

---

## 🚧 Future Improvements (optional)

- Dockerfile + docker-compose cluster
- gRPC transport instead of WebSockets
- Modular arithmetic (finite fields) for stronger information hiding
- Multiple job submissions per server instance
- Coded computing (straggler-robust polynomial codes)
- Horizontal scaling with Redis queue or Ray

---

## 📝 License

MIT
