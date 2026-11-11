"""The single background analysis run and its progress, which API clients poll."""

import logging
import threading
from datetime import datetime

logger = logging.getLogger(__name__)

_PROGRESS_FIELDS = {"total": 0, "done": 0, "skipped": 0, "judge_calls": 0, "judge_failures": 0,
                    "current": None, "error": None}


class AnalysisJob:
    def __init__(self):
        self._lock = threading.Lock()
        self._state = {"running": False, "phase": "idle", "mode": None, "started_at": None,
                       "last_run": None, **_PROGRESS_FIELDS}

    @property
    def running(self):
        return self._state["running"]

    def snapshot(self):
        with self._lock:
            return dict(self._state)

    def update(self, **fields):
        with self._lock:
            self._state.update(fields)

    def clear(self):
        self.update(phase="idle", last_run=None, **_PROGRESS_FIELDS)

    def start(self, mode, run):
        """Run `run(progress)` in a background thread unless one is already running.
        `run` returns the run summary. Returns whether a new run was started."""
        with self._lock:
            if self._state["running"]:
                return False
            self._state.update(running=True, phase="starting", mode=mode, **_PROGRESS_FIELDS,
                               started_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        threading.Thread(target=self._execute, args=(run,), daemon=True).start()
        return True

    def _execute(self, run):
        try:
            summary = run(lambda **status: self.update(**status))
            self.update(phase="done", last_run=summary)
        except Exception as exc:
            logger.exception("analysis run failed")
            self.update(phase="error", error=f"{type(exc).__name__}: {exc}")
        finally:
            self.update(running=False)
