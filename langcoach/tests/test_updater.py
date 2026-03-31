"""Tests for core/updater.py"""
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Allow running from langcoach/ directory
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.updater import (
    compare_versions,
    fetch_latest_release,
    get_local_version,
    UpdateInfo,
)


# ── compare_versions ──────────────────────────────────────────

def test_compare_newer():
    assert compare_versions("1.0.0", "1.1.0") is True

def test_compare_same():
    assert compare_versions("1.0.0", "1.0.0") is False

def test_compare_older():
    assert compare_versions("2.0.0", "1.9.9") is False

def test_compare_patch():
    assert compare_versions("1.0.0", "1.0.1") is True

def test_compare_major():
    assert compare_versions("1.9.9", "2.0.0") is True


# ── get_local_version ─────────────────────────────────────────

def test_get_local_version_reads_file(tmp_path):
    version_file = tmp_path / "version.txt"
    version_file.write_text("2.3.1\n")
    assert get_local_version(version_file) == "2.3.1"

def test_get_local_version_missing_file(tmp_path):
    assert get_local_version(tmp_path / "nope.txt") == "0.0.0"

def test_get_local_version_strips_whitespace(tmp_path):
    f = tmp_path / "version.txt"
    f.write_text("  1.2.3  \n")
    assert get_local_version(f) == "1.2.3"


# ── fetch_latest_release ──────────────────────────────────────

def _mock_urlopen(tag_name: str):
    """Returns a context manager that yields a fake GitHub API response."""
    payload = json.dumps({"tag_name": tag_name, "html_url": "https://example.com"}).encode()
    mock_resp = MagicMock()
    mock_resp.read.return_value = payload
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp

def test_fetch_latest_release_returns_update_info():
    with patch("urllib.request.urlopen", return_value=_mock_urlopen("v1.5.0")):
        info = fetch_latest_release("owner", "repo")
    assert info.latest_version == "1.5.0"
    assert info.release_url == "https://example.com"

def test_fetch_latest_release_strips_v_prefix():
    with patch("urllib.request.urlopen", return_value=_mock_urlopen("v2.0.0")):
        info = fetch_latest_release("owner", "repo")
    assert info.latest_version == "2.0.0"

def test_fetch_latest_release_no_prefix():
    with patch("urllib.request.urlopen", return_value=_mock_urlopen("3.1.0")):
        info = fetch_latest_release("owner", "repo")
    assert info.latest_version == "3.1.0"

def test_fetch_latest_release_network_error():
    with patch("urllib.request.urlopen", side_effect=Exception("timeout")):
        info = fetch_latest_release("owner", "repo")
    assert info is None
