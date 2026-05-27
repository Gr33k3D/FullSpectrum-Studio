#!/usr/bin/env python3
"""Run reproducible FullSpectrum planning variants on a local painted project."""

import argparse
import importlib.util
import json
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("fullspectrum_engine", ROOT / "fullspectrum_engine.py")
ENGINE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ENGINE)


def main():
    parser = argparse.ArgumentParser(description="Benchmark FullSpectrum quality-versus-waste variants")
    parser.add_argument("source")
    parser.add_argument("--reference")
    parser.add_argument("--palette-source", default="catalog",
                        choices=["inventory", "catalog", "all-bambu", "custom", "exact-cmykw"])
    parser.add_argument("--custom-palette")
    parser.add_argument("--output", help="Optional JSON output path")
    args = parser.parse_args()
    source = Path(args.source).expanduser().resolve()
    results = []
    with tempfile.TemporaryDirectory(prefix="fullspectrum_benchmark_") as folder:
        for label, bias in (("Practical", 20), ("Balanced", 60), ("Detail", 90)):
            converted = ENGINE.convert(
                source, "official", args.palette_source, Path(folder) / label, False, "auto",
                reference=args.reference, custom_catalog_path=args.custom_palette,
                quality_bias=bias, mix_model="perceptual",
            )
            results.append({
                "variant": label,
                "qualityBias": bias,
                "physicalSlots": converted["realSlots"],
                "mixedSlots": converted["printability"]["mixedSlots"],
                "paintedMixedShare": converted["printability"]["paintedMixedShare"],
                "estimatedDeltaE": converted["quality"]["estimatedDeltaE"],
                "qualityScore": converted["quality"]["qualityScore"],
                "confidenceScore": converted["quality"]["confidenceScore"],
                "contrastRetention": converted["quality"].get("contrastRetention"),
                "referenceSimilarityScore": converted["quality"].get("referenceSimilarityScore"),
                "difficulty": converted["printability"]["difficulty"],
                "validated": converted["validation"] == "OK",
            })
    payload = {
        "source": source.name,
        "reference": Path(args.reference).name if args.reference else None,
        "note": "FullSpectrum estimates are pre-slice planning values, not measured printed color or toolchange time.",
        "variants": results,
    }
    text = json.dumps(payload, indent=2)
    if args.output:
        Path(args.output).expanduser().write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
