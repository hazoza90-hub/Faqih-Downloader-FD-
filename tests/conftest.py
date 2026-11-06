import os
import sys
import importlib
import importlib.abc
import importlib.util

# Ensure project root and src/ are in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

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

# Fix Windows Tcl/Tk library paths to prevent intermittent TclError
tcl_dir = os.path.join(sys.base_prefix, "tcl", "tcl8.6")
tk_dir = os.path.join(sys.base_prefix, "tcl", "tk8.6")
if os.path.isdir(tcl_dir):
    os.environ["TCL_LIBRARY"] = tcl_dir
if os.path.isdir(tk_dir):
    os.environ["TK_LIBRARY"] = tk_dir

try:
    import time
    import tkinter as tk
    _RealTk = tk.Tk

    class SafeTk(_RealTk):
        """Wraps tk.Tk with retry logic to withstand transient Windows Tcl file locking."""
        def __init__(self, *args, **kwargs):
            last_err = None
            for attempt in range(5):
                try:
                    super().__init__(*args, **kwargs)
                    return
                except Exception as e:
                    last_err = e
                    time.sleep(0.08)
            if last_err:
                raise last_err

    tk.Tk = SafeTk
except Exception:
    pass
