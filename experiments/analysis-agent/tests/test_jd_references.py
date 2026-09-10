import pytest

def test_unissued_reference_cannot_be_resolved():
    from analysis_agent.jd_references import IssuedReferences
    from analysis_agent.jd_types import JdScope
    refs=IssuedReferences(JdScope('a'),{})
    with pytest.raises(ValueError,match='issued'):
        refs.require('guessed-real-id','target')
