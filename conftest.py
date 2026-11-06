import os
import sys
import tempfile
import importlib
import importlib.abc
import importlib.util

_SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if os.path.isdir(_SRC_DIR) and _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

# In-memory backwards compatibility alias for legacy 'smart_download' imports
class _SmartDownloadAliasLoader(importlib.abc.Loader):
    def __init__(self, target_name: str):
        self.target_name = target_name

    def create_module(self, spec):
        mod = importlib.import_module(self.target_name)
        sys.modules[spec.name] = mod
        return mod

    def exec_module(self, module):
        pass


class _SmartDownloadAliasFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname: str, path=None, target=None):
        if fullname == "smart_download" or fullname.startswith("smart_download."):
            target_name = "faqih_downloader" + fullname[14:]
            try:
                spec = importlib.util.find_spec(target_name)
                if spec is not None:
                    alias_spec = importlib.util.spec_from_loader(
                        fullname,
                        _SmartDownloadAliasLoader(target_name),
                        origin=spec.origin,
                        is_package=spec.submodule_search_locations is not None,
                    )
                    alias_spec.submodule_search_locations = spec.submodule_search_locations
                    return alias_spec
            except Exception:
                pass
        return None


if not any(isinstance(f, _SmartDownloadAliasFinder) for f in sys.meta_path):
    sys.meta_path.insert(0, _SmartDownloadAliasFinder())

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
