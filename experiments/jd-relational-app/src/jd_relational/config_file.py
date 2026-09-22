"""Small current-user DPAPI file boundary, not a settings or database owner.

The caller supplies one trusted absolute path and owns host/initialization
exclusion. A permanent empty sibling guard records that initialization started;
its non-shared handle also serializes file publication. Never delete that guard
or automatically adopt a backup/candidate. A failed write is unconfirmed, even
when a later read can establish the persisted contents. No power-loss guarantee
or transaction spanning this file and PostgreSQL is implied.
"""

from contextlib import closing
import ctypes
from pathlib import Path
import sys
from uuid import uuid4


MAX_PLAINTEXT_BYTES = 64 * 1024
# DPAPI has framing overhead. Bound its input independently of the plaintext.
MAX_PROTECTED_BYTES = 80 * 1024
_CODES = frozenset({
    "invalid_configuration_path", "invalid_configuration_bytes",
    "configuration_missing", "configuration_exists", "configuration_busy",
    "configuration_invalid", "configuration_changed", "configuration_unavailable",
    "configuration_read_failed", "configuration_protection_failed",
    "configuration_write_unconfirmed",
})


class ConfigFileError(ValueError):
    def __init__(self, code: str):
        self.code = code if code in _CODES else "configuration_unavailable"
        super().__init__(self.code)


def _windows():
    if sys.platform != "win32":
        raise ConfigFileError("configuration_unavailable")
    import win32file
    return win32file


def default_config_path() -> Path:
    """Resolve the OS known folder without creating directories or files."""
    try:
        _windows()
        from win32com.shell import shell, shellcon
        return Path(shell.SHGetKnownFolderPath(shellcon.FOLDERID_LocalAppData, 0, None)) / "Caliburn" / "JDRelational" / "host.v1.dpapi"
    except Exception:
        raise ConfigFileError("configuration_unavailable") from None


def _validate_bytes(value: bytes):
    if type(value) is not bytes or not 0 < len(value) <= MAX_PLAINTEXT_BYTES:
        raise ConfigFileError("invalid_configuration_bytes")


def _unprotect(blob: bytes) -> bytes:
    try:
        import win32crypt
        import win32cryptcon
        _, plaintext = win32crypt.CryptUnprotectData(
            blob, None, None, None, win32cryptcon.CRYPTPROTECT_UI_FORBIDDEN,
        )
        if type(plaintext) is not bytes or not 0 < len(plaintext) <= MAX_PLAINTEXT_BYTES:
            raise ValueError()
        return plaintext
    except Exception:
        raise ConfigFileError("configuration_invalid") from None


def _protect(plaintext: bytes) -> bytes:
    _validate_bytes(plaintext)
    try:
        _windows()
        import win32crypt
        import win32cryptcon
        protected = win32crypt.CryptProtectData(
            plaintext, "Caliburn JD local configuration v1", None, None, None,
            win32cryptcon.CRYPTPROTECT_UI_FORBIDDEN,
        )
        if not 0 < len(protected) <= MAX_PROTECTED_BYTES or _unprotect(protected) != plaintext:
            raise ValueError()
        return protected
    except Exception:
        raise ConfigFileError("configuration_protection_failed") from None


def _open(path, access, share, disposition):
    native = _windows()
    try:
        handle = native.CreateFile(str(path), access, share, None, disposition,
                                   native.FILE_FLAG_OPEN_REPARSE_POINT, None)
    except Exception as error:
        code = getattr(error, "winerror", None)
        if code in (2, 3):
            raise ConfigFileError("configuration_missing") from None
        if code in (80, 183):
            raise ConfigFileError("configuration_exists") from None
        if code in (32, 33):
            raise ConfigFileError("configuration_busy") from None
        raise ConfigFileError("configuration_unavailable") from None
    try:
        # NULL security attributes use the native inherited DACL and produce a
        # non-inheritable handle. Reject alternate leaf identities, not ACLs.
        import win32api
        import win32con
        info = native.GetFileInformationByHandle(handle)
        if (info[0] & (native.FILE_ATTRIBUTE_DIRECTORY | win32con.FILE_ATTRIBUTE_REPARSE_POINT)
                or info[7] != 1 or win32api.GetHandleInformation(handle) & win32con.HANDLE_FLAG_INHERIT):
            raise ConfigFileError("configuration_invalid")
        return handle
    except Exception:
        handle.Close()
        raise ConfigFileError("configuration_invalid") from None


def _read_handle(handle) -> bytes:
    native = _windows()
    size = native.GetFileSize(handle)
    if not 0 < size <= MAX_PROTECTED_BYTES:
        raise ConfigFileError("configuration_invalid")
    native.SetFilePointer(handle, 0, native.FILE_BEGIN)
    code, blob = native.ReadFile(handle, size + 1)
    if code != 0 or len(blob) != size:
        raise ConfigFileError("configuration_invalid")
    return blob


def _write_checked(handle, protected: bytes, plaintext: bytes):
    native = _windows()
    code, written = native.WriteFile(handle, protected)
    if code != 0 or written != len(protected):
        raise ConfigFileError("configuration_write_unconfirmed")
    native.FlushFileBuffers(handle)
    persisted = _read_handle(handle)
    if persisted != protected or _unprotect(persisted) != plaintext:
        raise ConfigFileError("configuration_write_unconfirmed")


def _replace_file(target: Path, candidate: Path, backup: Path):
    # pywin32 b312's wrapper reverses these two path arguments (verified with
    # synthetic native files). Bind this one documented Win32 API directly;
    # do not reverse App arguments to depend on an upstream wrapper defect.
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    replace = kernel.ReplaceFileW
    replace.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_wchar_p,
                        ctypes.c_uint32, ctypes.c_void_p, ctypes.c_void_p]
    replace.restype = ctypes.c_int
    if not replace(str(target), str(candidate), str(backup), 0, None, None):
        # Read immediately; no OS message, filename, or plaintext leaves here.
        error = ctypes.get_last_error()
        del error
        raise ConfigFileError("configuration_write_unconfirmed")


class ConfigFile:
    __slots__ = ("_path", "_guard")

    def __init__(self, path: Path):
        if not isinstance(path, Path) or not path.is_absolute() or ".." in path.parts or not path.name:
            raise ConfigFileError("invalid_configuration_path")
        self._path = path
        self._guard = path.with_name(path.name + ".lock")

    def __repr__(self):
        return "<ConfigFile>"

    def read(self) -> bytes:
        """Read one stable file identity; no mkdir, lock creation, or fallback."""
        try:
            native = _windows()
            with closing(_open(self._path, native.GENERIC_READ, native.FILE_SHARE_READ, native.OPEN_EXISTING)) as handle:
                return _unprotect(_read_handle(handle))
        except ConfigFileError:
            raise
        except Exception:
            raise ConfigFileError("configuration_read_failed") from None

    def create(self, plaintext: bytes) -> None:
        """One explicit initialization attempt, never a missing-file repair."""
        protected = _protect(plaintext)
        try:
            native = _windows()
            self._path.parent.mkdir(parents=True, exist_ok=True)
            # Even a crash between these two creates leaves an initialization
            # sentinel. A later create must not allocate a new installation.
            with closing(_open(self._guard, native.GENERIC_READ | native.GENERIC_WRITE, 0, native.CREATE_NEW)) as guard:
                native.FlushFileBuffers(guard)
                with closing(_open(self._path, native.GENERIC_READ | native.GENERIC_WRITE, 0, native.CREATE_NEW)) as handle:
                    _write_checked(handle, protected, plaintext)
        except ConfigFileError:
            raise
        except Exception:
            raise ConfigFileError("configuration_write_unconfirmed") from None

    def replace(self, plaintext: bytes, *, expected: bytes) -> None:
        """Replace existing config under file CAS and caller-owned host lease.

        Candidates and backups remain on failure. A backup is evidence, never
        an automatic fallback. Concurrent mutations fail immediately as busy.
        """
        _validate_bytes(expected)
        protected = _protect(plaintext)
        try:
            native = _windows()
            with closing(_open(self._guard, native.GENERIC_READ | native.GENERIC_WRITE, 0, native.OPEN_EXISTING)) as guard:
                if native.GetFileSize(guard) != 0:
                    raise ConfigFileError("configuration_invalid")
                if self.read() != expected:
                    raise ConfigFileError("configuration_changed")
                suffix = uuid4().hex  # A filename only; never an installation/key.
                candidate = self._path.with_name(self._path.name + "." + suffix + ".candidate")
                backup = self._path.with_name(self._path.name + "." + suffix + ".backup")
                with closing(_open(candidate, native.GENERIC_READ | native.GENERIC_WRITE, 0, native.CREATE_NEW)) as handle:
                    _write_checked(handle, protected, plaintext)
                _replace_file(self._path, candidate, backup)
                if self.read() != plaintext:
                    raise ConfigFileError("configuration_write_unconfirmed")
        except ConfigFileError:
            raise
        except Exception:
            raise ConfigFileError("configuration_write_unconfirmed") from None
