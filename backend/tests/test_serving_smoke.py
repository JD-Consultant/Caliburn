from app.graph_v3.serving import AGENT_NAME, build_demo_sdk


def test_demo_sdk_builds_and_registers_agent():
    sdk = build_demo_sdk()
    names = [a.name for a in sdk.agents]
    assert AGENT_NAME in names
