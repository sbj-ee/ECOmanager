import pytest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from eco_manager import ECO


@pytest.fixture
def eco_system(tmp_path):
    db_path = tmp_path / "test_eco.db"
    attachments_dir = tmp_path / "test_attachments"
    return ECO(db_path=str(db_path), attachments_dir=str(attachments_dir))
