"""
settings package for Faqih Downloader (FD).
Provides dark theme application settings dialog and handlers.
"""
from .layout_builder import SettingsModalLayoutMixin
from .sniffer_handlers import SettingsSnifferHandlersMixin
from .storage_handlers import SettingsStorageHandlersMixin
from .network_system_handlers import SettingsNetworkSystemMixin
from .modal import SettingsModal, _BaseToplevel

__all__ = [
    "SettingsModalLayoutMixin",
    "SettingsSnifferHandlersMixin",
    "SettingsStorageHandlersMixin",
    "SettingsNetworkSystemMixin",
    "SettingsModal",
    "_BaseToplevel",
]
