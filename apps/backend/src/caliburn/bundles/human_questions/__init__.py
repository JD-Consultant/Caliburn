"""人工提問 Bundle 的公開組裝入口。"""

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict

from caliburn.bundles.human_questions.ask_user_question import create_question_tool
from caliburn.bundles.interview.services import INTERVIEW_UOW_FACTORY, MODEL_REFERENCES
from caliburn.modules.agent.plugins.contracts import AgentBundle, AgentPlugin


class _Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")


def create_bundle(config: Mapping[str, object]) -> AgentBundle:
    _Settings.model_validate(config)
    return AgentBundle(
        plugins=(
            AgentPlugin(
                "human_questions",
                tools=(create_question_tool(),),
                required_services=(INTERVIEW_UOW_FACTORY, MODEL_REFERENCES),
                required_plugins=("interview",),
            ),
        )
    )
