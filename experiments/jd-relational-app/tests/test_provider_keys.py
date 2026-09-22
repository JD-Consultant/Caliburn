"""Provider keys live in Windows Credential Manager, and only there.

Real Credential Manager for this Windows user, under targets this test owns and
removes again. No provider is called, no configuration file is read or written,
and no key is ever printed or written to an artifact.
"""

from contextlib import contextmanager
import os
import sys

import pytest

from jd_relational import provider_keys
from jd_relational.provider_keys import (
    MAX_KEY_CHARACTERS, ROLES, TARGETS, ProviderKeyError, configured_roles,
    read_key, remove_key, store_key,
)

pytestmark = pytest.mark.skipif(sys.platform != "win32",
                                reason="Windows Credential Manager evidence")

SECRET = "synthetic-not-a-real-provider-key-0001"


@pytest.fixture
def owned(monkeypatch):
    """Test-only targets, always removed again whatever the test does."""
    targets = {role: f"Caliburn JD TEST {os.getpid()}/{role}" for role in ROLES}
    monkeypatch.setattr(provider_keys, "TARGETS", targets)
    try:
        yield targets
    finally:
        for role in targets:
            remove_key(role)


def test_a_role_with_no_key_is_simply_not_configured(owned):
    assert read_key("openrouter") is None
    assert configured_roles() == {"openrouter": False}


def test_a_stored_key_comes_back_exactly_and_survives_a_replacement(owned):
    store_key("openrouter", SECRET)
    assert read_key("openrouter") == SECRET
    store_key("openrouter", SECRET + "-replaced")
    assert read_key("openrouter") == SECRET + "-replaced"


def test_old_direct_provider_names_are_not_secret_roles(owned):
    for role in ("openai", "anthropic"):
        with pytest.raises(ProviderKeyError) as error:
            read_key(role)
        assert error.value.code == "unknown_provider_role"


def test_removing_the_key_disables_ai(owned):
    store_key("openrouter", SECRET)
    assert remove_key("openrouter") is True
    assert read_key("openrouter") is None
    assert remove_key("openrouter") is False, "already absent is not an error"


@pytest.mark.parametrize("bad", ["", "   ", "x" * (MAX_KEY_CHARACTERS + 1), None, 1])
def test_an_unusable_key_is_refused_before_it_is_stored(owned, bad):
    with pytest.raises(ProviderKeyError) as error:
        store_key("openrouter", bad)
    assert error.value.code == "invalid_provider_key"
    assert read_key("openrouter") is None


def test_an_unknown_role_has_no_store_at_all(owned):
    for call in (lambda: read_key("gemini"), lambda: store_key("gemini", SECRET),
                 lambda: remove_key("gemini")):
        with pytest.raises(ProviderKeyError) as error:
            call()
        assert error.value.code == "unknown_provider_role"


def test_errors_and_repr_never_carry_the_key(owned):
    try:
        store_key("openrouter", "x" * (MAX_KEY_CHARACTERS + 1))
    except ProviderKeyError as error:
        assert "x" * 20 not in str(error) and "x" * 20 not in repr(error)
    store_key("openrouter", SECRET)
    assert SECRET not in repr(configured_roles())


def test_the_real_targets_are_named_for_this_app():
    assert set(TARGETS) == {"openrouter"}
    assert all(name.startswith("Caliburn JD/") for name in TARGETS.values())
    assert len(set(TARGETS.values())) == 1


def test_checking_configuration_touches_no_provider_and_no_config_file(owned, monkeypatch):
    import jd_relational.config_file as config_file

    def forbidden(*args, **kwargs):
        raise AssertionError("checking keys must not read the local configuration")

    monkeypatch.setattr(config_file.ConfigFile, "read", forbidden)
    store_key("openrouter", SECRET)
    assert configured_roles() == {"openrouter": True}


def test_the_operator_commands_never_print_a_key(owned, capsys, monkeypatch):
    """Setting a key reports the capability, never the value."""
    from jd_relational.__main__ import main
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("getpass.getpass", lambda prompt="": SECRET)
    assert main(["set-key", "--service", "openrouter"]) == 0
    printed = capsys.readouterr()
    assert SECRET not in printed.out and SECRET not in printed.err
    assert "Windows 認證管理員" in printed.out and "備份不會匯出金鑰" in printed.out
    assert read_key("openrouter") == SECRET

    assert main(["remove-key", "--service", "openrouter"]) == 0
    assert SECRET not in capsys.readouterr().out
    assert read_key("openrouter") is None


def test_a_non_interactive_set_refuses_rather_than_taking_a_key_from_argv(owned, monkeypatch):
    from jd_relational.__main__ import main
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    assert main(["set-key", "--service", "openrouter"]) == 1
    assert read_key("openrouter") is None


def test_set_and_remove_need_the_service_named(owned):
    from jd_relational.__main__ import main
    assert main(["set-key"]) == 2 and main(["remove-key"]) == 2


@contextmanager
def failing(name, winerror):
    """Fail the way Windows really does, and undo only this one patch.

    A shared monkeypatch would also revert the fixture's test targets, which
    would send the cleanup at a real credential and leak the test one.
    """
    import pywintypes
    import win32cred

    def explode(*args, **kwargs):
        raise pywintypes.error(winerror, name, "synthetic credential failure")

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(win32cred, name, explode)
        yield


ACCESS_DENIED = 5


def test_a_credential_store_failure_is_not_reported_as_no_key(owned):
    """Absent and unreadable are different answers; only one may say 'not set'."""
    store_key("openrouter", SECRET)
    with failing("CredRead", ACCESS_DENIED):
        with pytest.raises(ProviderKeyError) as error:
            read_key("openrouter")
    assert error.value.code == "credential_store_unavailable"


def test_status_does_not_claim_not_configured_when_it_could_not_look(owned):
    store_key("openrouter", SECRET)
    with failing("CredRead", ACCESS_DENIED):
        with pytest.raises(ProviderKeyError):
            configured_roles()


def test_a_removal_that_did_not_happen_is_never_reported_as_already_absent(owned):
    """Telling the operator the key was never there would leave the secret behind."""
    store_key("openrouter", SECRET)
    with failing("CredDelete", ACCESS_DENIED):
        with pytest.raises(ProviderKeyError) as error:
            remove_key("openrouter")
        assert error.value.code == "credential_delete_failed"
    assert read_key("openrouter") == SECRET, "the key really is still there"


def test_removing_a_key_that_is_genuinely_absent_is_still_success(owned):
    assert remove_key("openrouter") is False


def test_a_non_interactive_set_says_there_is_nowhere_to_type(owned, capsys, monkeypatch):
    from jd_relational.__main__ import main
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    assert main(["set-key", "--service", "openrouter"]) == 1
    printed = capsys.readouterr().err
    assert "需要可輸入的終端機" in printed
    assert "不符合格式" not in printed, "a missing terminal is not a malformed key"
