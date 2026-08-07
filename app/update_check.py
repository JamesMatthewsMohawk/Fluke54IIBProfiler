"""Check GitHub Releases for a newer version than this build.

Uses urllib (stdlib) rather than adding a dependency just for one GET
request. Every failure mode (no internet, GitHub down, unexpected JSON,
a malformed version string) must fail silently and return None -- a
failed update check is not something to bother the user with, only a
found update is.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

from app.version import __version__

GITHUB_REPO = "JamesMatthewsMohawk/Fluke54IIBProfiler"
LATEST_RELEASE_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
RELEASES_PAGE_URL = f"https://github.com/{GITHUB_REPO}/releases/latest"
REQUEST_TIMEOUT_S = 5.0


@dataclass(frozen=True)
class ReleaseInfo:
    version: str  # e.g. "1.0.7", tag's leading "v" stripped
    url: str


def parse_version(version: str) -> tuple[int, ...]:
    """'v1.0.7' or '1.0.7' -> (1, 0, 7). Non-numeric parts become 0, so an
    unparseable string sorts as (0, 0, 0) rather than raising."""
    digits = re.findall(r"\d+", version)
    return tuple(int(d) for d in digits) if digits else (0,)


def is_newer(candidate: str, current: str) -> bool:
    return parse_version(candidate) > parse_version(current)


def fetch_latest_release() -> ReleaseInfo | None:
    request = urllib.request.Request(
        LATEST_RELEASE_API_URL,
        headers={"User-Agent": "SuperbaTunnelProfiler", "Accept": "application/vnd.github+json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_S) as response:
            data = json.load(response)
        tag = str(data["tag_name"]).lstrip("vV")
        url = str(data.get("html_url") or RELEASES_PAGE_URL)
        return ReleaseInfo(version=tag, url=url)
    except Exception:  # noqa: BLE001 -- any failure here just means "no notice", never an error dialog
        return None


def check_for_update() -> ReleaseInfo | None:
    """Returns the latest release's info if it's newer than this build, else None."""
    release = fetch_latest_release()
    if release is not None and is_newer(release.version, __version__):
        return release
    return None
