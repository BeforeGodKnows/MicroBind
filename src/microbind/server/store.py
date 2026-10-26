"""Small-team queue: SQLite WAL, transactional claims, heartbeat and bounded backlog."""

import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path


class Store:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        with self.db() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
              CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, path TEXT NOT NULL,
                builtin INTEGER NOT NULL, created REAL NOT NULL);
              CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, project_id TEXT NOT NULL, kind TEXT NOT NULL,
                options TEXT NOT NULL, status TEXT NOT NULL, stage TEXT NOT NULL,
                created REAL NOT NULL, updated REAL NOT NULL, error TEXT);
            """)

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.root / "microbind.db", timeout=20)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def add_project(self, name, path, builtin=False, id=None):
        id = id or uuid.uuid4().hex
        with self.db() as db:
            db.execute(
                "INSERT OR IGNORE INTO projects VALUES (?,?,?,?,?)",
                (id, name, str(path), int(builtin), time.time()),
            )
        return id

    def projects(self):
        with self.db() as db:
            return [dict(r) for r in db.execute("SELECT * FROM projects ORDER BY created DESC")]

    def project(self, id):
        with self.db() as db:
            r = db.execute("SELECT * FROM projects WHERE id=?", (id,)).fetchone()
        return dict(r) if r else None

    @staticmethod
    def decode(r):
        d = dict(r)
        d["options"] = json.loads(d["options"])
        return d

    def jobs(self):
        with self.db() as db:
            return [
                self.decode(r)
                for r in db.execute("SELECT * FROM jobs ORDER BY created DESC LIMIT 200")
            ]

    def job(self, id):
        with self.db() as db:
            r = db.execute("SELECT * FROM jobs WHERE id=?", (id,)).fetchone()
        return self.decode(r) if r else None

    def enqueue(self, project_id, kind, options):
        id, now = uuid.uuid4().hex, time.time()
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            if (
                db.execute(
                    "SELECT count(*) FROM jobs WHERE status IN ('queued','running')"
                ).fetchone()[0]
                >= 20
            ):
                raise ValueError("队列已满，请等待现有任务完成")
            db.execute(
                "INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    id,
                    project_id,
                    kind,
                    json.dumps(options),
                    "queued",
                    "等待工作进程",
                    now,
                    now,
                    None,
                ),
            )
        return id

    def claim(self, kind):
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            # A dead process is failed, not silently replayed. The user can submit a new job.
            db.execute(
                "UPDATE jobs SET status='failed',stage='工作进程中断',error='heartbeat expired',updated=? WHERE status='running' AND updated<?",
                (time.time(), time.time() - 120),
            )
            r = db.execute(
                "SELECT * FROM jobs WHERE status='queued' AND kind=? ORDER BY created LIMIT 1",
                (kind,),
            ).fetchone()
            if r:
                db.execute(
                    "UPDATE jobs SET status='running',stage='准备分析',updated=? WHERE id=?",
                    (time.time(), r["id"]),
                )
        return self.decode(r) if r else None

    def update(self, id, *, status=None, stage=None, error=None):
        with self.db() as db:
            db.execute(
                "UPDATE jobs SET status=coalesce(?,status),stage=coalesce(?,stage),error=coalesce(?,error),updated=? WHERE id=?",
                (status, stage, error, time.time(), id),
            )

    def cancel_queued(self, id):
        with self.db() as db:
            return db.execute(
                "UPDATE jobs SET status='cancelled',stage='已取消',updated=? WHERE id=? AND status='queued'",
                (time.time(), id),
            ).rowcount

    def delete(self, id):
        with self.db() as db:
            return db.execute(
                "DELETE FROM jobs WHERE id=? AND status NOT IN ('running','queued')", (id,)
            ).rowcount
