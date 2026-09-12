"""Only synthetic configuration-file subprocess probes; no host or provider."""

from pathlib import Path
import sys

from jd_relational import config_file as module


mode, raw_path, label = sys.argv[1:]
file = module.ConfigFile(Path(raw_path))
payload = ("synthetic-config-" + label).encode("ascii")


def pause():
    print("ready", flush=True)
    if sys.stdin.readline().strip() != "go":
        raise RuntimeError("probe_input_missing")


try:
    if mode == "create":
        pause()
        file.create(payload)
        print("created", flush=True)
    elif mode == "read":
        print("matches" if file.read() == payload else "mismatch", flush=True)
    elif mode == "hold_create":
        original = module._write_checked
        def held(*args):
            pause()
            return original(*args)
        module._write_checked = held
        file.create(payload)
        print("created", flush=True)
    elif mode == "hold_replace":
        original = module._replace_file
        def held(*args):
            pause()
            return original(*args)
        module._replace_file = held
        file.replace(payload, expected=b"synthetic-config-old")
        print("replaced", flush=True)
    else:
        raise RuntimeError("probe_mode_invalid")
except module.ConfigFileError as error:
    print(error.code, flush=True)
