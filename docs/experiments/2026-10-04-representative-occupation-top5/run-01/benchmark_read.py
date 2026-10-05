"""Wait only for a transient Windows bind-mount sharing lock; never hide bad JSON."""
import time
from pipeline import read

def ready_read(path, deadline):
    while True:
        try:
            return read(path)
        except PermissionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(.02)
