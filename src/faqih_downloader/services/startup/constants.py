"""
Windows startup registry keys and Task Scheduler constants for Faqih Downloader.
"""
WINDOWS_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
STARTUP_REG_KEY_NAME = "FaqihDownloader"
LEGACY_STARTUP_REG_KEY_NAME = "SmartDownload"
TASK_NAME = "FaqihDownloaderAutoStart"
LEGACY_TASK_NAME = "SmartDownloadAutoStart"
STARTUP_APPROVED_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"
STARTUP_APPROVED_FOLDER_KEY = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\StartupFolder"
EXPLORER_SERIALIZE_KEY = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Serialize"
ENABLED_STARTUP_BINARY = b"\x02" + b"\x00" * 11
