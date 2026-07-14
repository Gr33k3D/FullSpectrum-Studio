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
        return "0.4.14"


APP_VERSION = release_version()


def privacy_safe_error_message(message):
    text = str(message or "Conversion failed.").strip()
    lowered = text.lower()
    sensitive_markers = (
        str(Path.home()).lower(),
        "/users/",
        "/home/",
        "\\users\\",
        "remaininggrams",
        '"spools"',
        "catalogsource",
        ".3mf",
        ".obj",
        ".glb",
        ".json",
    )
    windows_absolute_path = len(text) > 2 and text[1:3] in (":\\", ":/")
    if windows_absolute_path or any(marker and marker in lowered for marker in sensitive_markers):
        return "Conversion failed. Technical details are available in the private local log."
    return text[:800]


def format_shareable_error_report(message, log_created=False):
    lines = [
        "FullSpectrum Studio conversion error",
        "",
        "Conversion failed. Technical details are available in the private local log.",
        "",
        "The exception text, local paths, model names, inventory data, and raw engine output were excluded.",
    ]
    if log_created:
        lines.append("A detailed diagnostic log was saved locally and is not included here.")
    return "\n".join(lines)


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
        f"Quality: {quality['qualityScore']:.1f} / 100   Mean dE: {quality['estimatedDeltaE']:.2f}   Max dE: {quality['maximumDeltaE']:.2f}",
        f"Confidence: {quality['confidenceScore']:.1f} / 100   Mixed paint: {printability['paintedMixedShare']:.1f}%",
        f"Printability: {printability['difficulty']}",
        f"Physical anchors: {anchors}",
    ]
    lines.extend(f"Suggestion: {item}" for item in printability.get("recommendations", []))
    lines.extend(f"Warning: {warning}" for warning in result.get("warnings", []))
    return "\n".join(lines)
