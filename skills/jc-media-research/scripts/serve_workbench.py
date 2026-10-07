#!/usr/bin/env python3
"""Serve one task's writing state on loopback, with atomic revision-checked saves."""
from __future__ import annotations
import argparse
from copy import deepcopy
import fcntl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import tempfile
from threading import Lock
sys.path.insert(0, str(Path(__file__).resolve().parent))
from research_decisions import DecisionError, now, read_json, refresh_section, render_workbench, validate_workbench

class Conflict(DecisionError):
    pass

def atomic_write(path, text):
    path = Path(path)
    fd, name = tempfile.mkstemp(prefix="." + path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name): os.unlink(name)

def update_state(current, payload):
    if not isinstance(payload, dict) or set(payload) != {"revision", "sections"}:
        raise DecisionError("保存只接受 revision 与 sections")
    if type(payload["revision"]) is not int or payload["revision"] != current["revision"]:
        raise Conflict("页面版本已变化，本地输入已保留")
    if not isinstance(payload["sections"], list): raise DecisionError("sections 无效")
    edits = {}
    for row in payload["sections"]:
        if not isinstance(row, dict) or set(row) != {"id", "mine", "note"}: raise DecisionError("只能编辑稿件和批注")
        if row["id"] in edits: raise DecisionError("重复的段落 id")
        if not isinstance(row["mine"], str) or not isinstance(row["note"], str): raise DecisionError("稿件和批注必须是文字")
        if len(row["mine"]) > 100000 or len(row["note"]) > 100000: raise DecisionError("单段超过保存上限")
        edits[row["id"]] = row
    if set(edits) != {s["id"] for s in current["sections"]}: raise DecisionError("段落集合不能变化")
    updated = deepcopy(current)
    changes, stamp = [], now()
    for section in updated["sections"]:
        edit = edits[section["id"]]
        if section.get("locked") and edit["mine"] != section["mine"]: raise DecisionError("已锁定段落保持原文")
        if (edit["mine"], edit["note"]) == (section["mine"], section.get("note", "")): continue
        before = {"mine": section["mine"], "note": section.get("note", "")}
        after = {"mine": edit["mine"], "note": edit["note"]}
        section.setdefault("history", []).append({"at": stamp, "revision": current["revision"], **before})
        section.update(after)
        if before["mine"] != after["mine"]: refresh_section(section, updated["sources"])
        changes.append({"section_id": section["id"], "before": before, "after": after})
    if not changes: return current
    updated["revision"] += 1
    updated["updated_at"] = stamp
    updated.setdefault("history", []).append({"at": stamp, "revision": updated["revision"], "changes": changes})
    validate_workbench(updated)
    return updated

def save_task(task_dir, payload):
    task_dir = Path(task_dir)
    with (task_dir / ".save.lock").open("a") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        current = read_json(task_dir / "state.json")
        updated = update_state(current, payload)
        page = render_workbench(updated)
        if updated is not current:
            atomic_write(task_dir / "state.json", json.dumps(updated, ensure_ascii=False, indent=2) + "\n")
        try:
            atomic_write(task_dir / "writing.html", page)
            report_updated, report_error = True, None
        except OSError:
            report_updated, report_error = False, "内容已保存，HTML 更新失败；重启服务可由 state.json 重建"
        return {"state": updated, "report_updated": report_updated, "report_error": report_error}

def make_server(task_dir, port=8767):
    task_dir = Path(task_dir).resolve()
    state = read_json(task_dir / "state.json")
    validate_workbench(state)
    atomic_write(task_dir / "writing.html", render_workbench(state))
    mutex = Lock()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args): pass
        def send(self, status, body, kind="application/json"):
            data = (json.dumps(body, ensure_ascii=False) if kind == "application/json" else body).encode()
            self.send_response(status)
            self.send_header("Content-Type", kind + "; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        def do_GET(self):
            if self.path == "/api/state": self.send(200, read_json(task_dir / "state.json"))
            elif self.path in {"/", "/writing.html"}:
                self.send(200, (task_dir / "writing.html").read_text(encoding="utf-8"), "text/html")
            else: self.send(404, {"error": "not found"})
        def do_POST(self):
            if self.path != "/api/save": self.send(404, {"error": "not found"}); return
            origin = f"http://127.0.0.1:{self.server.server_port}"
            if self.headers.get("Origin") != origin or self.headers.get("X-Workbench-Save") != "1":
                self.send(403, {"error": "同源保存校验失败"}); return
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                self.send(415, {"error": "需要 JSON"}); return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 2 * 1024 * 1024: raise DecisionError("保存内容大小无效")
                payload = json.loads(self.rfile.read(size))
                with mutex: result = save_task(task_dir, payload)
                self.send(200, result)
            except Conflict as exc:
                self.send(409, {"error": str(exc), "revision": read_json(task_dir / "state.json")["revision"]})
            except (DecisionError, ValueError, TypeError) as exc:
                self.send(400, {"error": str(exc)})
            except OSError:
                self.send(500, {"error": "保存失败，本地输入保留"})
    return ThreadingHTTPServer(("127.0.0.1", port), Handler)

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--port", type=int, default=8767)
    args = parser.parse_args(argv)
    server = make_server(args.task_dir, args.port)
    print(f"http://127.0.0.1:{server.server_port}/", flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
