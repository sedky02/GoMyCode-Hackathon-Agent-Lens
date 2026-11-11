import threading
import time

from agentlens.job import AnalysisJob


def wait_until_idle(job):
    deadline = time.time() + 5
    while job.running:
        assert time.time() < deadline
        time.sleep(0.01)


def test_only_one_run_at_a_time_and_progress_is_visible():
    job = AnalysisJob()
    release = threading.Event()

    def run(progress):
        progress(phase="analyzing", total=3, done=1)
        release.wait(5)
        return {"run_id": 1, "analyzed": 3}

    assert job.start("rules", run) is True
    assert job.start("rules", run) is False
    deadline = time.time() + 5
    while job.snapshot()["phase"] != "analyzing":
        assert time.time() < deadline
        time.sleep(0.01)
    assert job.snapshot()["done"] == 1

    release.set()
    wait_until_idle(job)
    status = job.snapshot()
    assert (status["phase"], status["last_run"]) == ("done", {"run_id": 1, "analyzed": 3})
    assert job.start("rules", run) is True
    wait_until_idle(job)


def test_a_failing_run_reports_the_error_and_frees_the_job():
    job = AnalysisJob()

    def run(progress):
        raise ValueError("boom")

    job.start("rules", run)
    wait_until_idle(job)
    status = job.snapshot()
    assert (status["phase"], status["error"]) == ("error", "ValueError: boom")
