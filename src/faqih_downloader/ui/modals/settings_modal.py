"""
Backward-compatibility shim for settings_modal.
Logic has moved to faqih_downloader.ui.modals.settings.
"""
from .settings import (
    SettingsModal,
    _BaseToplevel,
    SettingsModalLayoutMixin,
    SettingsSnifferHandlersMixin,
    SettingsStorageHandlersMixin,
    SettingsNetworkSystemMixin,
)

__all__ = [
    "SettingsModal",
    "_BaseToplevel",
    "SettingsModalLayoutMixin",
    "SettingsSnifferHandlersMixin",
    "SettingsStorageHandlersMixin",
    "SettingsNetworkSystemMixin",
]
