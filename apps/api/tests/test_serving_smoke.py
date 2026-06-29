from app.authoring.serving import AGENT_NAME, build_demo_agent


def test_demo_agent_builds_with_name():
    agent = build_demo_agent()
    assert agent.name == AGENT_NAME
