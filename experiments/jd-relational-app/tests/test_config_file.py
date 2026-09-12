"""Synthetic native Windows configuration files; never use LocalAppData secrets."""

from pathlib import Path
import os
import queue
import subprocess
import sys
import threading
import traceback

import pytest

from jd_relational.config_file import ConfigFile, ConfigFileError
from jd_relational import config_file as module


pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows DPAPI only")


def test_missing_read_does_not_initialize(tmp_path):
    path = tmp_path / "never-created" / "host.v1.dpapi"
    with pytest.raises(ConfigFileError, match="^configuration_missing$"):
        ConfigFile(path).read()
    assert not path.parent.exists()


def test_create_replace_keeps_exact_plaintext_and_backup(tmp_path):
    path = tmp_path / "config" / "host.v1.dpapi"
    old, new = b'{"synthetic":"old-value"}', b'{"synthetic":"new-value"}'
    file = ConfigFile(path)
    file.create(old)
    assert file.read() == old and old not in path.read_bytes()
    with pytest.raises(ConfigFileError, match="^configuration_exists$"):
        file.create(new)
    file.replace(new, expected=old)
    assert file.read() == new
    backups = list(path.parent.glob("*.backup"))
    assert len(backups) == 1 and ConfigFile(backups[0]).read() == old


def test_guard_survives_missing_target_and_prevents_new_installation(tmp_path):
    path = tmp_path / "host.v1.dpapi"
    file = ConfigFile(path)
    file.create(b"synthetic original")
    path.unlink()
    with pytest.raises(ConfigFileError, match="^configuration_exists$"):
        file.create(b"synthetic different installation")
    with pytest.raises(ConfigFileError, match="^configuration_missing$"):
        file.replace(b"synthetic update", expected=b"synthetic original")
    assert not path.exists()


def test_default_path_uses_known_folder_without_creating_it(tmp_path, monkeypatch):
    from win32com.shell import shell, shellcon
    calls = []
    def known(folder, flags, token):
        calls.append((folder, flags, token))
        return str(tmp_path / "not-created")
    monkeypatch.setattr(shell, "SHGetKnownFolderPath", known)
    assert module.default_config_path() == tmp_path / "not-created" / "Caliburn" / "JDRelational" / "host.v1.dpapi"
    assert calls == [(shellcon.FOLDERID_LocalAppData, 0, None)]
    assert not (tmp_path / "not-created").exists()


@pytest.mark.parametrize("plaintext", [b"", "text", bytearray(b"x"), b"x" * (65536 + 1)],
                         ids=["empty", "text", "bytearray", "too_large"])
def test_invalid_plaintext_has_no_filesystem_effect(tmp_path, plaintext):
    path = tmp_path / "absent" / "config"
    with pytest.raises(ConfigFileError, match="^invalid_configuration_bytes$"):
        ConfigFile(path).create(plaintext)
    assert not path.parent.exists()


def test_full_plaintext_limit_includes_room_for_dpapi_framing(tmp_path):
    path = tmp_path / "config"
    plaintext = b"x" * module.MAX_PLAINTEXT_BYTES
    ConfigFile(path).create(plaintext)
    assert ConfigFile(path).read() == plaintext
    assert module.MAX_PLAINTEXT_BYTES < path.stat().st_size <= module.MAX_PROTECTED_BYTES


@pytest.mark.parametrize("corruption", ["empty", "truncate", "flip", "large"])
def test_corrupt_config_is_not_overwritten_or_fallback(tmp_path, corruption):
    path = tmp_path / "config"
    file = ConfigFile(path)
    file.create(b"old synthetic value")
    file.replace(b"current synthetic value", expected=b"old synthetic value")
    blob = path.read_bytes()
    corrupted = {"empty": b"", "truncate": blob[:len(blob)//2],
                 "flip": blob[:-1] + bytes([blob[-1] ^ 1]),
                 "large": b"x" * (module.MAX_PROTECTED_BYTES + 1)}[corruption]
    path.write_bytes(corrupted)
    with pytest.raises(ConfigFileError, match="^configuration_invalid$"):
        file.read()
    with pytest.raises(ConfigFileError, match="^configuration_invalid$"):
        file.replace(b"replacement", expected=b"current synthetic value")
    with pytest.raises(ConfigFileError, match="^configuration_exists$"):
        file.create(b"replacement")
    assert path.read_bytes() == corrupted and len(list(tmp_path.glob("*.backup"))) == 1


def test_oversized_ciphertext_is_rejected_before_dpapi(tmp_path, monkeypatch):
    path = tmp_path / "config"
    path.write_bytes(b"x" * (module.MAX_PROTECTED_BYTES + 1))
    def forbidden(*args):
        raise AssertionError("No decrypt for an oversized input")
    monkeypatch.setattr(module, "_unprotect", forbidden)
    with pytest.raises(ConfigFileError, match="^configuration_invalid$"):
        ConfigFile(path).read()


def test_replace_needs_both_guard_and_current_file(tmp_path):
    path = tmp_path / "config"
    path.write_bytes(module._protect(b"old"))
    with pytest.raises(ConfigFileError, match="^configuration_missing$"):
        ConfigFile(path).replace(b"new", expected=b"old")
    assert ConfigFile(path).read() == b"old"
    assert not path.with_name("config.lock").exists()


def test_stale_expected_does_not_publish_or_add_candidate(tmp_path):
    file = ConfigFile(tmp_path / "config")
    file.create(b"old")
    file.replace(b"new", expected=b"old")
    before = set(tmp_path.iterdir())
    with pytest.raises(ConfigFileError, match="^configuration_changed$"):
        file.replace(b"stale overwrite", expected=b"old")
    assert file.read() == b"new" and set(tmp_path.iterdir()) == before


def test_read_uses_native_share_rules_for_one_file_identity(tmp_path):
    import win32file
    import win32api
    import win32con
    path = tmp_path / "config"
    ConfigFile(path).create(b"synthetic")
    handle = module._open(path, win32file.GENERIC_READ, win32file.FILE_SHARE_READ, win32file.OPEN_EXISTING)
    try:
        assert not win32api.GetHandleInformation(handle) & win32con.HANDLE_FLAG_INHERIT
        assert ConfigFile(path).read() == b"synthetic"
        with pytest.raises(Exception) as deletion:
            path.unlink()
        assert getattr(deletion.value, "winerror", None) == 32
        with pytest.raises(Exception) as writer:
            win32file.CreateFile(str(path), win32file.GENERIC_WRITE, win32file.FILE_SHARE_READ,
                                 None, win32file.OPEN_EXISTING, 0, None)
        assert getattr(writer.value, "winerror", None) == 32
    finally:
        handle.Close()


def test_failed_initial_write_leaves_nonrenewable_sentinel(tmp_path, monkeypatch):
    path = tmp_path / "config"
    def failed(*args):
        raise OSError("SyntheticPrivateWritePathAndSecret")
    monkeypatch.setattr(module, "_write_checked", failed)
    with pytest.raises(ConfigFileError, match="^configuration_write_unconfirmed$") as caught:
        ConfigFile(path).create(b"synthetic")
    assert "SyntheticPrivateWritePathAndSecret" not in "".join(traceback.format_exception(caught.value))
    assert path.exists() and path.stat().st_size == 0
    with pytest.raises(ConfigFileError, match="^configuration_exists$"):
        ConfigFile(path).create(b"second")
    with pytest.raises(ConfigFileError, match="^configuration_invalid$"):
        ConfigFile(path).read()


@pytest.mark.parametrize("phase", ["write", "flush", "readback", "publish"])
def test_failed_replace_keeps_old_file_and_candidate(tmp_path, monkeypatch, phase):
    import win32file
    path = tmp_path / "config"
    file = ConfigFile(path)
    file.create(b"old")
    original_blob = path.read_bytes()
    def failed(*args):
        raise OSError("SyntheticPrivateReplacementSentinel")
    with monkeypatch.context() as scope:
        if phase == "write":
            scope.setattr(win32file, "WriteFile", failed)
        elif phase == "flush":
            scope.setattr(win32file, "FlushFileBuffers", failed)
        elif phase == "readback":
            original = module._read_handle
            calls = []
            def fail_second(handle):
                calls.append(True)
                return original(handle) if len(calls) == 1 else failed()
            scope.setattr(module, "_read_handle", fail_second)
        else:
            scope.setattr(module, "_replace_file", failed)
        with pytest.raises(ConfigFileError, match="^configuration_write_unconfirmed$") as caught:
            file.replace(b"new", expected=b"old")
    assert "SyntheticPrivateReplacementSentinel" not in "".join(traceback.format_exception(caught.value))
    assert path.read_bytes() == original_blob and file.read() == b"old"
    assert len(list(tmp_path.glob("*.candidate"))) == 1
    assert not list(tmp_path.glob("*.backup"))


def test_real_replacement_lost_ack_is_unconfirmed_and_new_value_can_be_read(tmp_path, monkeypatch):
    file = ConfigFile(tmp_path / "config")
    file.create(b"old")
    original = module._replace_file
    def lose_ack(*args):
        original(*args)
        raise OSError("SyntheticPrivateAcknowledgement")
    monkeypatch.setattr(module, "_replace_file", lose_ack)
    with pytest.raises(ConfigFileError, match="^configuration_write_unconfirmed$"):
        file.replace(b"new", expected=b"old")
    assert file.read() == b"new"
    with pytest.raises(ConfigFileError, match="^configuration_changed$"):
        file.replace(b"new", expected=b"old")
    backup, = tmp_path.glob("*.backup")
    assert ConfigFile(backup).read() == b"old"


def _worker(mode, path, label):
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(Path(__file__).parents[1] / "src")
    return subprocess.Popen(
        [sys.executable, str(Path(__file__).with_name("config_file_worker.py")), mode, str(path), label],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        creationflags=subprocess.CREATE_NO_WINDOW, env=environment,
    )


def _stop(process):
    if process.poll() is None:
        process.terminate()
    process.communicate(timeout=10)


def _ready(process):
    output = queue.Queue()
    threading.Thread(target=lambda: output.put(process.stdout.readline()), daemon=True).start()
    assert output.get(timeout=10).strip() == "ready"


def test_two_native_processes_create_exactly_one_configuration(tmp_path):
    path = tmp_path / "config"
    processes = [_worker("create", path, label) for label in ("one", "two")]
    try:
        for process in processes:
            _ready(process)
        for process in processes:
            process.stdin.write("go\n")
            process.stdin.flush()
        results = [process.communicate(timeout=10) for process in processes]
        assert all(process.returncode == 0 for process in processes)
        assert all(error == "" for _, error in results)
        assert sorted(out.strip() for out, _ in results) == ["configuration_exists", "created"]
        assert ConfigFile(path).read() in (b"synthetic-config-one", b"synthetic-config-two")
    finally:
        for process in processes:
            _stop(process)


def test_new_process_decrypts_same_user_configuration(tmp_path):
    path = tmp_path / "config"
    ConfigFile(path).create(b"synthetic-config-restart")
    process = _worker("read", path, "restart")
    try:
        stdout, stderr = process.communicate(timeout=10)
        assert process.returncode == 0 and stdout.strip() == "matches" and stderr == ""
    finally:
        _stop(process)


def test_creator_process_death_leaves_truncated_file_and_guard(tmp_path):
    path = tmp_path / "config"
    process = _worker("hold_create", path, "abandoned")
    try:
        _ready(process)
        with pytest.raises(ConfigFileError, match="^configuration_busy$"):
            ConfigFile(path).read()
        process.terminate()
        process.communicate(timeout=10)
        with pytest.raises(ConfigFileError, match="^configuration_invalid$"):
            ConfigFile(path).read()
        with pytest.raises(ConfigFileError, match="^configuration_exists$"):
            ConfigFile(path).create(b"new installation forbidden")
    finally:
        _stop(process)


def test_live_replacer_is_exclusive_and_death_keeps_old_file(tmp_path):
    path = tmp_path / "config"
    file = ConfigFile(path)
    file.create(b"synthetic-config-old")
    process = _worker("hold_replace", path, "new")
    try:
        _ready(process)
        assert file.read() == b"synthetic-config-old"
        with pytest.raises(ConfigFileError, match="^configuration_busy$"):
            file.replace(b"second", expected=b"synthetic-config-old")
        process.terminate()
        process.communicate(timeout=10)
        assert file.read() == b"synthetic-config-old"
        assert len(list(tmp_path.glob("*.candidate"))) == 1
        file.replace(b"explicit next attempt", expected=b"synthetic-config-old")
        assert file.read() == b"explicit next attempt"
    finally:
        _stop(process)


def test_safe_reprs_and_dpapi_failure_do_not_publish(tmp_path, monkeypatch):
    import win32crypt
    secret = b"SyntheticPrivatePlaintext"
    path = tmp_path / "SyntheticPrivatePath" / "config"
    def failed(*args):
        raise OSError("SyntheticPrivatePlatformError")
    monkeypatch.setattr(win32crypt, "CryptProtectData", failed)
    file = ConfigFile(path)
    with pytest.raises(ConfigFileError, match="^configuration_protection_failed$") as caught:
        file.create(secret)
    output = repr(file) + repr(caught.value) + "".join(traceback.format_exception(caught.value))
    assert all(sentinel not in output for sentinel in ["SyntheticPrivatePlaintext", "SyntheticPrivatePath", "SyntheticPrivatePlatformError"])
    assert not path.parent.exists()


def test_dpapi_calls_forbid_ui_and_use_current_user(tmp_path, monkeypatch):
    import win32crypt
    import win32cryptcon
    protect, unprotect = win32crypt.CryptProtectData, win32crypt.CryptUnprotectData
    calls = []
    def protected(*args):
        assert args[2:5] == (None, None, None)
        assert args[5] == win32cryptcon.CRYPTPROTECT_UI_FORBIDDEN
        calls.append("protect")
        return protect(*args)
    def unprotected(*args):
        assert args[1:4] == (None, None, None)
        assert args[4] == win32cryptcon.CRYPTPROTECT_UI_FORBIDDEN
        calls.append("unprotect")
        return unprotect(*args)
    monkeypatch.setattr(win32crypt, "CryptProtectData", protected)
    monkeypatch.setattr(win32crypt, "CryptUnprotectData", unprotected)
    file = ConfigFile(tmp_path / "config")
    file.create(b"synthetic")
    assert file.read() == b"synthetic"
    assert calls.count("protect") == 1 and calls.count("unprotect") >= 2


def test_native_replace_false_is_safe_and_does_not_read_error_message(monkeypatch, tmp_path):
    calls = []
    class NativeFailure:
        def __call__(self, *args):
            calls.append(args)
            return 0
    class Library:
        ReplaceFileW = NativeFailure()
    monkeypatch.setattr(module.ctypes, "WinDLL", lambda name, use_last_error: Library())
    def get_error():
        calls.append("GetLastError")
        return 5
    monkeypatch.setattr(module.ctypes, "get_last_error", get_error)
    with pytest.raises(ConfigFileError, match="^configuration_write_unconfirmed$") as caught:
        module._replace_file(tmp_path / "SyntheticPrivateTarget", tmp_path / "SyntheticPrivateCandidate", tmp_path / "SyntheticPrivateBackup")
    assert len(calls) == 2 and calls[-1] == "GetLastError"
    assert calls[0][3:] == (0, None, None)
    assert "SyntheticPrivateTarget" not in repr(caught.value)


def test_nonempty_guard_is_not_reinterpreted_or_cleared(tmp_path):
    path = tmp_path / "config"
    file = ConfigFile(path)
    file.create(b"old")
    guard = path.with_name("config.lock")
    guard.write_bytes(b"unknown nonsecret marker")
    with pytest.raises(ConfigFileError, match="^configuration_invalid$"):
        file.replace(b"new", expected=b"old")
    assert file.read() == b"old" and guard.read_bytes() == b"unknown nonsecret marker"
