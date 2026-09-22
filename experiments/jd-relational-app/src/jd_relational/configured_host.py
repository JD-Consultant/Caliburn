"""Explicit setup and ordinary open for one protected local installation.

Every call that acquires a Windows host belongs to a dedicated process. Failure
does not authorize trying another installation key in the same process. File
phase changes and PostgreSQL setup are deliberately not claimed as one ACID txn.
"""
from dataclasses import dataclass

from .config_file import ConfigFile
from .host_runtime import ManualHost, open_manual_host
from .local_configuration import (LocalConfiguration, ConfigurationError, new_configuration,
    parse_configuration, encode_configuration, configuration_phase)
from .references import ReferenceCodec
from .windows_host import bootstrap_host


def _unchanged(file, expected):
    if file.read() != expected:
        raise ConfigurationError("configuration_changed")


def initialize_configuration(file: ConfigFile, *, connection: dict | None = None,
                             resume: bool = False) -> LocalConfiguration:
    """Operator-requested initialization; never called by ordinary open."""
    from .storage_setup import check_empty_database, setup_database
    if type(resume) is not bool or (resume and connection is not None) or (not resume and type(connection) is not dict):
        raise ConfigurationError("configuration_invalid")
    if not resume:
        file.create(encode_configuration(new_configuration(**connection)))
    raw = file.read()
    settings = parse_configuration(raw)
    if settings.phase == "ready":
        raise ConfigurationError("configuration_already_ready")
    if settings.phase == "maintenance":
        raise ConfigurationError("configuration_maintenance")
    lease = bootstrap_host(settings.installation_id)
    lease.require_previous_stopped()
    _unchanged(file, raw)  # A file may have changed while waiting for the host.
    if settings.phase == "initialization_pending":
        check_empty_database(settings)
        lease.require_previous_stopped()
        next_settings = configuration_phase(settings, "initializing")
        next_raw = encode_configuration(next_settings)
        file.replace(next_raw, expected=raw)
        _unchanged(file, next_raw)
        settings, raw = next_settings, next_raw
    setup_database(settings, lease)
    lease.require_previous_stopped()
    ready = configuration_phase(settings, "ready")
    ready_raw = encode_configuration(ready)
    file.replace(ready_raw, expected=raw)
    _unchanged(file, ready_raw)
    return ready


@dataclass(frozen=True, repr=False)
class ConfiguredHost:
    settings: LocalConfiguration
    host: ManualHost
    codec: ReferenceCodec

    def close(self, *, timeout=10):
        return self.host.close(timeout=timeout)


def open_configured_host(file: ConfigFile, *, consultant) -> ConfiguredHost:
    """Reads fixed settings only; no key creation, setup or environment override."""
    raw = file.read()
    settings = parse_configuration(raw)
    if settings.phase != "ready":
        raise ConfigurationError("configuration_maintenance" if settings.phase == "maintenance"
                                 else "configuration_initialization_required")
    codec = ReferenceCodec(settings.signing_key_bytes(), settings.dataset_id)
    host = open_manual_host(settings.installation_id, settings.database_url(),
        checkpoint_schema=settings.checkpoint_schema, consultant=consultant,
        _configuration_check=lambda: _unchanged(file, raw))
    return ConfiguredHost(settings, host, codec)
