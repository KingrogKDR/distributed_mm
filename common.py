# common.py
# Shared message types / helpers

import json

MSG_REGISTER = "register"
MSG_REQUEST = "request_task"
MSG_TASK = "task"
MSG_NO_TASK = "no_task"
MSG_RESULT = "result"

def make_message(msg_type: str, body: dict = None) -> str:
    m = {"type": msg_type}
    if body is not None:
        m["body"] = body
    return json.dumps(m)

def parse_message(raw: str) -> dict:
    return json.loads(raw)
