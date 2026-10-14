"""Versioned, local-only desktop preferences (no model or inventory snapshots)."""

import json
import os
import sys
import tempfile
from pathlib import Path

SETTINGS_VERSION = 1

CHOICES = {
    "strategy": {"official", "cmykw"},
    "planner_mode": {"best", "fast"},
    "planning_sample": {"paint", "preview"},
    "source": {"inventory", "catalog", "all-bambu", "custom", "exact-cmykw"},
    "catalog_region": {"global", "eu", "us-ca", "uk", "au-nz", "asia"},
    "real_slots": {"auto", "2", "3", "4", "5", "6", "7", "8"},
    "mix_model": {"bambu"},
    "output_application": {"Bambu Studio", "OrcaSlicer"},
}
BOOL_FIELDS = ("smart_quality", "auto_preview", "auto_open")
ANCHOR_FIELDS = ("disabled_anchor_keys", "pinned_anchor_keys")


def settings_path():
    """Use a per-user, writable directory, including in packaged builds."""
    if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        base = Path(os.environ["LOCALAPPDATA"])
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "FullSpectrumStudio" / "settings.json"


def validated_settings(data):
    """Discard unknown, obsolete, and incorrectly typed fields."""
    if not isinstance(data, dict) or data.get("version", SETTINGS_VERSION) != SETTINGS_VERSION:
        return {}
    clean = {}
    for field, allowed in CHOICES.items():
        if isinstance(data.get(field), str) and data[field] in allowed:
            clean[field] = data[field]
    custom = data.get("custom")
    if isinstance(custom, str) and len(custom) <= 8192 and "\x00" not in custom:
        clean["custom"] = custom
    for field in BOOL_FIELDS:
        if isinstance(data.get(field), bool):
            clean[field] = data[field]
    bias = data.get("quality_bias")
    if type(bias) is int and 0 <= bias <= 100:
        clean["quality_bias"] = bias
    for field in ANCHOR_FIELDS:
        keys = data.get(field)
        if isinstance(keys, list) and all(isinstance(key, str) and 0 < len(key) <= 256 for key in keys):
            clean[field] = sorted(set(keys))[:1000]
    return clean


def load_settings(path=None):
    """Missing/malformed settings never prevent a desktop launch."""
    destination = Path(path) if path is not None else settings_path()
    try:
        raw = json.loads(destination.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return {}
    return validated_settings(raw)


def save_settings(data, path=None):
    """Atomically write vetted fields so a crash cannot truncate preferences."""
    destination = Path(path) if path is not None else settings_path()
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": SETTINGS_VERSION, **validated_settings(data)}
    fd, temporary = tempfile.mkstemp(prefix=".settings-", suffix=".tmp", dir=destination.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return destination
