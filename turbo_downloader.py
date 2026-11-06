"""
Backward compatibility entry-point for Faqih Downloader (FD) / فقيه التنزيلات.
Maintained for backward compatibility with legacy scripts and tests.
All logic and symbols are imported directly from faqih_downloader.
"""
import sys
import os
import types
import importlib.util

_root = os.path.dirname(os.path.abspath(__file__))
_src_dir = os.path.join(_root, "src")
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

_root_file = os.path.join(_root, "faqih_downloader.py")
if os.path.isfile(_root_file):
    _spec = importlib.util.spec_from_file_location("faqih_downloader_root", _root_file)
    _fd = importlib.util.module_from_spec(_spec)
    sys.modules["faqih_downloader_root"] = _fd
    _spec.loader.exec_module(_fd)
else:
    try:
        import faqih_downloader as _fd
    except Exception:
        _fd = None

# Export all public symbols from _fd into this module
for _k, _v in getattr(_fd, "__dict__", {}).items():
    if not _k.startswith("__"):
        globals()[_k] = _v


class _TurboDownloaderCompatShim(types.ModuleType):
    def __getattr__(self, name):
        if _fd is not None and hasattr(_fd, name):
            val = getattr(_fd, name)
            setattr(self, name, val)
            return val
        raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if name.startswith("__") or _fd is None:
            return
        try:
            setattr(_fd, name, value)
        except Exception:
            pass


if __name__ in sys.modules:
    sys.modules[__name__].__class__ = _TurboDownloaderCompatShim

if __name__ == "__main__":
    if _fd is not None and hasattr(_fd, "early_single_instance_guard"):
        _fd.early_single_instance_guard()
        _fd.main()
