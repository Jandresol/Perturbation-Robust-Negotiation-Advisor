import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture
def cfg():
    return yaml.safe_load((ROOT / "configs" / "default.yaml").read_text())
