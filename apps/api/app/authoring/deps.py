from dataclasses import dataclass

from app.core.ports import KnowledgeClient, LlmPort, PersistPort


@dataclass
class Deps:
    knowledge: KnowledgeClient
    persist: PersistPort
    llm: LlmPort | None = None
