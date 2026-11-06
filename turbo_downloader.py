"""
Backward compatibility entry-point for Faqih Downloader (FD) / فقيه التنزيلات.
Maintained for backward compatibility with legacy scripts and tests.
All logic and symbols are imported directly from faqih_downloader.
"""
import sys
import os
import types

_root = os.path.dirname(os.path.abspath(__file__))
if _root not in sys.path:
    sys.path.insert(0, _root)

from faqih_downloader import *
import faqih_downloader as _fd


class _TurboDownloaderCompatShim(types.ModuleType):
    def __getattr__(self, name):
        return getattr(_fd, name)

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if name.startswith("__"):
            return
        try:
            setattr(_fd, name, value)
        except Exception:
            pass


sys.modules[__name__].__class__ = _TurboDownloaderCompatShim

if __name__ == "__main__":
    _fd.early_single_instance_guard()
    _fd.main()
