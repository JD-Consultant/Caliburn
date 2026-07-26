"""Job Authoring Core — canonical employee/AI co-authored job document.

Greenfield modular-monolith module introduced by ADR 0038 and the
2026-07-23 minimal authoring core plan. The pure core (contracts, commands,
canonical, transitions, digest, errors) imports only the standard library and
Pydantic; it must not import SQLAlchemy, FastAPI, provider SDKs, the interview
vNext domain, the OCS contract, or any Web DTO.
"""
