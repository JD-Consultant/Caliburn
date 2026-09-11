"""Managed test installation enters real bootstrap before pytest/DB/native."""
import os
import sys
from analysis_agent.windows_lifecycle import bootstrap

bootstrap(os.environ['Q019_LIFECYCLE_INSTALLATION'])
import pytest
raise SystemExit(pytest.main(sys.argv[1:]))
