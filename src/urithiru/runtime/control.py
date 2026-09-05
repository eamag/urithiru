import fcntl
import signal
from contextlib import contextmanager
from pathlib import Path
from threading import Event, Thread


class Cancelled(RuntimeError):
    pass


@contextmanager
def run_lock(directory: Path):
    with (directory / ".run.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another process is using this checkpoint directory") from None
        yield


@contextmanager
def cancellation(directory: Path):
    stop, done = Event(), Event()

    def watch():
        while not done.wait(0.5):
            if (directory / "cancel").exists():
                stop.set()
                return

    def interrupt(_signum, _frame):
        stop.set()

    previous = {sig: signal.signal(sig, interrupt) for sig in (signal.SIGINT, signal.SIGTERM)}
    thread = Thread(target=watch, daemon=True)
    thread.start()
    try:
        yield stop
    finally:
        done.set()
        thread.join()
        for sig, handler in previous.items():
            signal.signal(sig, handler)
