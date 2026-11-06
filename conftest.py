import os
import sys
import tempfile

_SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if os.path.isdir(_SRC_DIR) and _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

os.environ["SD_TESTING"] = "1"
if not os.environ.get("SD_CONFIG_DIR"):
    _isolated_dir = os.path.join(tempfile.gettempdir(), "sd_test_isolated_cfg")
    os.makedirs(_isolated_dir, exist_ok=True)
    os.environ["SD_CONFIG_DIR"] = _isolated_dir

try:
    import pytest

    @pytest.fixture(autouse=True)
    def isolate_test_environment(tmp_path, monkeypatch):
        test_cfg = str(tmp_path / "sd_cfg")
        os.makedirs(test_cfg, exist_ok=True)
        monkeypatch.setenv("SD_TESTING", "1")
        monkeypatch.setenv("SD_CONFIG_DIR", test_cfg)
        yield
except ImportError:
    pass
