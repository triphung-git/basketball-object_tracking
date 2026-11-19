"""Small, process-shared leases for local dashboard workers and projections."""
from __future__ import annotations

from contextlib import contextmanager, closing
import os
from pathlib import Path
import sqlite3
import time
import threading
import uuid


def process_alive(pid):
    if not pid:
        return False
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x1000, False, int(pid))
        if not handle:
            return ctypes.get_last_error() == 5
        try:
            code = wintypes.DWORD()
            return bool(kernel.GetExitCodeProcess(handle, ctypes.byref(code)) and code.value == 259)
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(int(pid), 0)
        return True
    except PermissionError:
        return True
    except (OSError, ValueError):
        return False


class SharedJobs:
    def __init__(self, root):
        self.local = threading.local()
        self.path = Path(root)/'dashboard-state.sqlite3'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as connection:
            connection.execute('PRAGMA journal_mode=WAL')
            connection.execute('''CREATE TABLE IF NOT EXISTS leases (
                slot TEXT PRIMARY KEY, token TEXT NOT NULL, job_id TEXT NOT NULL,
                owner TEXT NOT NULL, pid INTEGER, state TEXT NOT NULL,
                revision TEXT, updated REAL NOT NULL)''')
            connection.commit()

    def connect(self):
        connection = sqlite3.connect(self.path, timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA busy_timeout=15000')
        return connection

    @contextmanager
    def atomic(self):
        existing = getattr(self.local,'connection',None)
        if existing is not None:
            yield existing
            return
        connection = self.connect()
        try:
            connection.execute('BEGIN IMMEDIATE')
            self.local.connection = connection
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            self.local.connection = None
            connection.close()

    def get(self, slot):
        with closing(self.connect()) as connection:
            row = connection.execute('SELECT * FROM leases WHERE slot=?', (slot,)).fetchone()
        return dict(row) if row else None

    @staticmethod
    def live(row):
        # Heartbeats plus process checks avoid treating a reused PID as the
        # original worker. Model initialization is monitored independently.
        return bool(row and row['state'] == 'running' and time.time()-row['updated'] < 120
                    and process_alive(row['pid']))

    def claim(self, slot, job_id, owner, revision=None):
        with self.atomic() as connection:
            row = connection.execute('SELECT * FROM leases WHERE slot=?', (slot,)).fetchone()
            if self.live(row):
                return None
            token = uuid.uuid4().hex
            connection.execute('INSERT OR REPLACE INTO leases VALUES (?,?,?,?,?,?,?,?)',
                (slot, token, job_id, owner, os.getpid(), 'running', revision, time.time()))
        return token

    def heartbeat(self, slot, token, pid=None):
        with self.atomic() as connection:
            updated = connection.execute('UPDATE leases SET updated=?,pid=COALESCE(?,pid) '
                'WHERE slot=? AND token=? AND state=?', (time.time(),pid,slot,token,'running')).rowcount
        return bool(updated)

    def finish(self, slot, token, state):
        with self.atomic() as connection:
            updated = connection.execute('UPDATE leases SET state=?,updated=? '
                'WHERE slot=? AND token=? AND state=?', (state,time.time(),slot,token,'running')).rowcount
        return bool(updated)
