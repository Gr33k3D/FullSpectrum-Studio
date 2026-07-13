import os
import sys
from pathlib import Path


APP_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))


def release_version():
    override = os.environ.get("FULLSPECTRUM_VERSION", "").strip()
    if override:
        return override.removeprefix("v")
    try:
        return (APP_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return "0.4.13"


APP_VERSION = release_version()


def format_plan_preview(result):
    quality = result["quality"]
    printability = result["printability"]
    anchors = ", ".join(
        f"{anchor['slot']}: {anchor['name']} ({anchor['color']})"
        for anchor in result.get("anchors", [])
    ) or "none"
    lines = [
        "Plan preview only. No 3MF was written.",
        f"Physical slots: {result['realSlots']}   Mixed slots: {result['outputSlots'] - result['realSlots']}",
        f"Quality: {quality['qualityScore']:.1f} / 100   Mean dE: {quality['estimatedDeltaE']:.2f}",
        f"Confidence: {quality['confidenceScore']:.1f} / 100   Mixed paint: {printability['paintedMixedShare']:.1f}%",
        f"Printability: {printability['difficulty']}",
        f"Physical anchors: {anchors}",
    ]
    lines.extend(f"Suggestion: {item}" for item in printability.get("recommendations", []))
    lines.extend(f"Warning: {warning}" for warning in result.get("warnings", []))
    return "\n".join(lines)
