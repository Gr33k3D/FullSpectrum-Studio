"""Selectable palette entries for the Windows color-selection dialog.

The full planning engine owns filament loading and identity normalization;
this adapter intentionally reuses that logic for both built-in and custom sources.
"""


def selectable_filament_options(engine, source, snapshot=None, custom_path=""):
    """Return deduplicated selector options for the selected filament source.

    Raises the engine's actionable custom-palette errors to the UI caller.
    Inventory and catalog options remain unavailable while inventory loads.
    """
    if source == "custom":
        if not custom_path:
            return []
        raw = [engine.anchor_option_payload(item) for item in engine.custom_palette(custom_path)]
    elif source in ("inventory", "catalog", "all-bambu"):
        if not snapshot:
            return []
        if source == "inventory":
            raw = [engine.anchor_option_payload(item) for item in engine.inventory_palette(snapshot)]
        else:
            raw = list(snapshot.get("anchorOptions") or [])
            if source == "catalog":
                core = {"PLA Basic", "PLA Matte", "PLA Silk+"}
                raw = [item for item in raw if item.get("series") in core]
    else:
        return []

    unique = {}
    for option in raw:
        key = option.get("key")
        if key and key not in unique:
            unique[key] = option
    return sorted(
        unique.values(),
        key=lambda item: (
            item.get("remainingGrams") is None,
            str(item.get("series") or ""),
            str(item.get("name") or ""),
        ),
    )
