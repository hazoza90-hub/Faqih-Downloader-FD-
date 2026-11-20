"""
Application identity, version, and remote update API endpoint constants.
"""

APP_NAME = "Faqih Downloader (FD)"
APP_ID = "SmartDownload"
APP_VERSION = "2.0.2"

GITHUB_REPO_OWNER = "hazoza90-hub"
GITHUB_REPO_NAME = "Faqih-Downloader-FD-"
GITHUB_LATEST_RELEASE_API = f"https://api.github.com/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/releases/latest"

YTDLP_PYPI_JSON_API = "https://pypi.org/pypi/yt-dlp/json"
YTDLP_GITHUB_LATEST_API = "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest"
YTDLP_GITHUB_RELEASES_API = YTDLP_GITHUB_LATEST_API
