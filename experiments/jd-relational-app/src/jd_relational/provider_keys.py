"""Provider API keys, kept by Windows Credential Manager and nowhere else.

The operator sets a key once; the backend reads it only at the moment it
assembles a model and hands it straight to the SDK's own `api_key` parameter.
A key never reaches a prompt, a conversation, Memory, a checkpoint, the JD
database, the front end, a log line or a diagnostic file, and it is never part
of an App data backup -- the local configuration file is untouched by this
module, so restoring a backup on another machine means setting the key again.

Each role is stored separately: the conversation consultant is pinned to
Anthropic and the background stages to OpenAI, so one being configured never
stands in for the other. A missing key means that capability is not enabled;
it is never a reason to switch provider, and checking configuration never
calls a provider.

Checked 2026-09-14: Windows Credential Manager generic credentials through
pywin32 312's `win32cred` (CredRead/CredWrite/CredDelete,
https://learn.microsoft.com/windows/win32/api/wincred/). CRED_PERSIST_LOCAL_MACHINE
keeps a credential for this Windows user on this machine across restarts. No
new dependency and no second secret store.
"""

import sys

# One target per role, named so they are recognisable in the Windows UI.
TARGETS = {
    "anthropic": "Caliburn JD/anthropic",
    "openai": "Caliburn JD/openai",
}
ROLES = tuple(TARGETS)
MAX_KEY_CHARACTERS = 512


class ProviderKeyError(ValueError):
    """A bounded, safe code. The key itself is never part of an error."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _target(role: str) -> str:
    if role not in TARGETS:
        raise ProviderKeyError("unknown_provider_role")
    if sys.platform != "win32":
        raise ProviderKeyError("credential_store_unavailable")
    return TARGETS[role]


def read_key(role: str) -> str | None:
    """This role's key, or None when the operator has not set one.

    Returning None is an ordinary answer, not a failure: the App stays usable
    for manual JD work and simply reports that capability as not configured.
    """
    target = _target(role)
    import pywintypes
    import win32cred
    try:
        found = win32cred.CredRead(target, win32cred.CRED_TYPE_GENERIC, 0)
    except pywintypes.error:
        # Not found, or this user cannot read it. Either way there is no key
        # here; the reason is never forwarded, because it can carry the target.
        return None
    blob = found.get("CredentialBlob")
    if not blob:
        return None
    try:
        value = bytes(blob).decode("utf-16-le")
    except (UnicodeError, TypeError, ValueError):
        raise ProviderKeyError("stored_key_unreadable") from None
    value = value.rstrip("\x00")
    if not value.strip() or len(value) > MAX_KEY_CHARACTERS:
        raise ProviderKeyError("stored_key_unreadable")
    return value


def store_key(role: str, key: str) -> None:
    """Set or replace this role's key. Writing one never reads or calls out."""
    target = _target(role)
    if not isinstance(key, str) or not key.strip() or len(key) > MAX_KEY_CHARACTERS:
        raise ProviderKeyError("invalid_provider_key")
    import pywintypes
    import win32cred
    try:
        win32cred.CredWrite({
            "Type": win32cred.CRED_TYPE_GENERIC,
            "TargetName": target,
            "UserName": role,
            "CredentialBlob": key,
            "Comment": "Caliburn JD provider key; set and removed by the operator.",
            "Persist": win32cred.CRED_PERSIST_LOCAL_MACHINE,
        }, 0)
    except pywintypes.error:
        raise ProviderKeyError("credential_write_failed") from None


def remove_key(role: str) -> bool:
    """Remove this role's key. Already absent is success, not an error."""
    target = _target(role)
    import pywintypes
    import win32cred
    try:
        win32cred.CredDelete(target, win32cred.CRED_TYPE_GENERIC, 0)
        return True
    except pywintypes.error:
        return False


def configured_roles() -> dict[str, bool]:
    """Which capabilities are enabled, without calling any provider.

    This is the one thing the status exit needs, and it deliberately answers
    from the credential store alone: a stored key is not proof that the key
    works, and finding out would cost money.
    """
    answer = {}
    for role in ROLES:
        try:
            answer[role] = read_key(role) is not None
        except ProviderKeyError:
            answer[role] = False
    return answer
