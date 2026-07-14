#!/usr/bin/env python3
"""
FullSpectrum Studio conversion and validation engine.

Paint is remapped by decoding BambuStudio's serialized TriangleSelector states.
It is never inferred from first-use ordering or a guessed paint code formula.
"""

import argparse
import colorsys
import csv
import hashlib
import json
import math
import os
import plistlib
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import traceback
import zipfile
import xml.etree.ElementTree as ET
from array import array
from pathlib import Path
from itertools import combinations
from collections import Counter, defaultdict
from functools import lru_cache
from bambu_mixer_model import blend_color_multi as bambu_blend_color_multi

BAMBU_PLA = [
    ("PLA Matte Ivory White", "#FFFFFF"),
    ("PLA Matte Bone White", "#CBC6B8"),
    ("PLA Matte Desert Tan", "#E8DBB7"),
    ("PLA Matte Dark Chocolate", "#4D3324"),
    ("PLA Matte Dark Blue", "#042F56"),
    ("PLA Matte Marine Blue", "#0078BF"),
    ("PLA Matte Lemon Yellow", "#F7E600"),
    ("PLA Matte Grass Green", "#61B33B"),
    ("PLA Matte Sakura Pink", "#FFB7C5"),
    ("PLA Matte Scarlet Red", "#C12E1F"),
    ("PLA Matte Ice Blue", "#A7D8F0"),
    ("PLA Matte Ash Gray", "#9B9B9B"),
    ("PLA Matte Charcoal", "#2F2F2F"),
    ("PLA Basic White", "#FFFFFF"),
    ("PLA Basic Black", "#000000"),
    ("PLA Basic Red", "#C12E1F"),
    ("PLA Basic Orange", "#F36C21"),
    ("PLA Basic Yellow", "#F4EE2A"),
    ("PLA Basic Green", "#00AE42"),
    ("PLA Basic Cyan", "#00AEEF"),
    ("PLA Basic Blue", "#0A2E8A"),
    ("PLA Basic Purple", "#8B00FF"),
    ("PLA Basic Indigo Purple", "#482960"),
    ("PLA Basic Gray", "#8E9089"),
    ("PLA Basic Silver", "#A6A9AA"),
    ("PLA Basic Beige", "#D6B58C"),
    ("PLA Silk+ Gold", "#F4A925"),
    ("PLA Silk+ Silver", "#C0C0C0"),
    ("PLA Silk+ Copper", "#B87333"),
    ("PLA Silk+ Rose Gold", "#B76E79"),
    ("PLA Silk+ Blue", "#1E5AA8"),
    ("PLA Silk+ Purple", "#6B3FA0"),
    ("PLA Silk+ Red", "#C61A1A"),
    ("PLA Silk+ Green", "#15803D"),
]
CMYK_TARGETS = [
    ("Cyan", "#00AEEF"),
    ("Magenta", "#EC008C"),
    ("Yellow", "#F4EE2A"),
    ("Black", "#000000"),
    ("White", "#FFFFFF"),
    ("Warm White", "#F5F0E8"),
]
# Bambu mixed filament slots are layer/sublayer halftones, not liquid blends:
# the saved slot references physical component filaments and a short cadence of
# ratios, then the viewer and human eye perceive those alternating layers as a
# new color. Keep this search discrete. Arbitrary ratios such as 30:70 imply
# longer cadence patterns and can suggest physical precision the uncalibrated
# model does not have. Fast uses short practical schedules; Best/high-fidelity
# adds denser but still bounded schedules and validates against Bambu's loaded
# FilamentMixer reconstruction.
R2 = [(0.25,0.75), (1/3,2/3), (0.5,0.5), (2/3,1/3), (0.75,0.25)]
R3 = [(.6,.2,.2),(.2,.6,.2),(.2,.2,.6),(.5,.3,.2),(.5,.2,.3),(.3,.5,.2),(.2,.5,.3),(.3,.2,.5),(.2,.3,.5),(.4,.4,.2),(.4,.2,.4),(.2,.4,.4),(1/3,1/3,1/3)]
R2_FINE = sorted(set(R2 + [(1/6,5/6), (0.2,0.8), (0.4,0.6), (0.6,0.4), (0.8,0.2), (5/6,1/6)]))
R3_FINE = sorted(set(
    R3 + [
        (a/denom, b/denom, (denom-a-b)/denom)
        for denom in (4, 5, 6)
        for a in range(1, denom-1)
        for b in range(1, denom-a)
        if denom-a-b > 0
    ]
))

MIN_ANCHOR_DE = 7.0
DIRECT_ANCHOR_DE = 4.5
MIN_MIX_GAIN = 1.0
MAX_RELIABLE_MIX_DE = 8.0
MAX_HIGH_QUALITY_MIX_DE = 14.0
CMYKW_ROLE_WARNING_DE = 10.0
PALETTE_MAX_ERROR_WEIGHT = 0.06
QUALITY_MAX_ERROR_WEIGHT = 1.2
MODEL_EXTRUDER_USAGE_FRACTION = 0.002
MAX_BAMBU_PAINT_SLOT = 32
PREVIEW_GRID_RESOLUTION = 72
MIN_REAL_SLOTS = 2
DEFAULT_AUTO_MAX_REAL_SLOTS = 6
MAX_REAL_SLOTS = 8
MAX_ARCHIVE_ENTRIES = 20000
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 2 * 1024 * 1024 * 1024
MAX_REFERENCE_BYTES = 600 * 1024 * 1024
MAX_IMPORT_FACES = 2_000_000
MAX_INTERACTIVE_PREVIEW_TRIANGLES = 750_000
OPTIMIZED_PREVIEW_GRID_RESOLUTION = 72


def release_version():
    override=os.environ.get("FULLSPECTRUM_VERSION","").strip()
    if override:
        return override.removeprefix("v")
    try:
        value=Path(__file__).resolve().with_name("VERSION").read_text(encoding="utf-8").strip()
        if re.fullmatch(r"\d+\.\d+\.\d+",value):
            return value
    except OSError:
        pass
    return "0.4.14"


APP_VERSION = release_version()
OUTPUT_VERSION = f"v{APP_VERSION}"
DEFAULT_QUALITY_BIAS = 60
SMART_QUALITY_CANDIDATES = (35, 50, 70, 85, 100)
SMART_QUALITY_PROBE = 70
ANCHOR_BEAM_WIDTH = 8
ANCHOR_POOL_LIMIT = 64
HIGH_FIDELITY_QUALITY = 90
HIGH_FIDELITY_ANCHOR_BEAM_WIDTH = 12
HIGH_FIDELITY_ANCHOR_POOL_LIMIT = 96
MIX_CACHE_SIZE = 262_144
DIST_CACHE_SIZE = 524_288
MIX_RECIPE_INDEX_CACHE_SIZE = 4096
ANCHOR_SCORE_HINT_CACHE_SIZE = 16
ANCHOR_SCORE_HINTS_PER_TARGET = 480
ANCHOR_SCORE_TRIPLE_NEIGHBORS = 30
LOCAL_OPTIMIZE_CANDIDATE_LIMIT = 10
CATALOG_REGIONS = {
    "global": "Global planning",
    "eu": "Europe",
    "us-ca": "United States / Canada",
    "uk": "United Kingdom",
    "au-nz": "Australia / New Zealand",
    "asia": "Asia",
}
MIX_MODELS = ("bambu",)
PLANNER_MODES = ("best", "fast")
PLANNING_SAMPLES = ("paint", "preview")
PREVIEW_USAGE_BLEND = 0.88
HEX_DIGITS = "0123456789ABCDEF"
PAINT_PATTERN = re.compile(r'paint_color="([^"]+)"')
PAINT_BYTES_PATTERN = re.compile(br'paint_color="[^"]+"')
PAINT_BYTES_VALUE_PATTERN = re.compile(br'(paint_color=)(["\'])([^"\']*)(\2)')
XML_ATTRIBUTE_PATTERN = re.compile(r'([A-Za-z_:][\w:.-]*)="([^"]*)"')
VERTEX_TAG_PATTERN = re.compile(r'<(?:[A-Za-z_][\w:.-]*:)?vertex\b[^>]*>')
TRIANGLE_TAG_PATTERN = re.compile(r'<(?:[A-Za-z_][\w:.-]*:)?triangle\b[^>]*>')
PROFILE_BY_FAMILY = {
    "PLA Basic": ("Bambu PLA Basic @BBL H2C 0.2 nozzle", "GFA00"),
    "PLA Matte": ("Bambu PLA Matte @BBL H2C 0.2 nozzle", "GFA01"),
    "PLA Silk": ("Bambu PLA Silk @BBL H2C 0.2 nozzle", "GFA05"),
    "PLA Silk+": ("Bambu PLA Silk+ @BBL H2C 0.2 nozzle", "GFA06"),
    "PLA Marble": ("Bambu PLA Marble @BBL H2C", "GFA07"),
    "PLA Sparkle": ("Bambu PLA Sparkle @BBL X1C", "GFA08"),
    "PLA Tough": ("Bambu PLA Tough @BBL H2S", "GFA09"),
    "PLA Tough+": ("Bambu PLA Tough+ @BBL H2D 0.6 nozzle", "GFA10"),
    "PLA Aero": ("Bambu PLA Aero @BBL H2S", "GFA11"),
    "PLA Glow": ("Bambu PLA Glow @base", "GFA12"),
    "PLA Dynamic": ("Bambu PLA Dynamic @BBL H2C 0.2 nozzle", "GFA13"),
    "PLA Galaxy": ("Bambu PLA Galaxy @BBL X2D 0.4 nozzle", "GFA15"),
    "PLA Wood": ("Bambu PLA Wood @base", "GFA16"),
    "PLA Translucent": ("Bambu PLA Translucent @BBL H2D 0.2 nozzle", "GFA17"),
    "PLA Lite": ("Bambu PLA Lite @BBL H2DP 0.2 nozzle", "GFA18"),
    "PLA Pure": ("Bambu PLA Pure @BBL P1P 0.2 nozzle", "GFA19"),
    "PLA-CF": ("Bambu PLA-CF @BBL X1C 0.8 nozzle", "GFA50"),
    "PLA Metal": ("Bambu PLA Metal @BBL X1C 0.2 nozzle", "GFA02"),
}
MIXED_PROFILE_ID, MIXED_FILAMENT_ID = PROFILE_BY_FAMILY["PLA Basic"]
BAMBU_STUDIO_CATALOG_LOCATIONS = [
    Path("/Applications/BambuStudio.app/Contents/Resources/profiles/BBL/filament/filaments_color_codes.json"),
    Path.home()/"Library"/"Application Support"/"BambuStudio"/"system"/"BBL"/"filament"/"filaments_color_codes.json",
    Path.home()/"Library"/"Application Support"/"BambuStudioBeta"/"system"/"BBL"/"filament"/"filaments_color_codes.json",
    Path.home()/"Library"/"Application Support"/"Bambu Suite"/"system"/"BBL"/"filament"/"filaments_color_codes.json",
    Path.home()/"Library"/"Application Support"/"OrcaSlicer"/"system"/"BBL"/"filament"/"filaments_color_codes.json",
]
BAMBU_STUDIO_APP_LOCATIONS = [
    Path("/Applications/BambuStudio.app"),
    Path("/Applications/Bambu Studio.app"),
    Path.home()/"Applications"/"BambuStudio.app",
    Path.home()/"Applications"/"Bambu Studio.app",
]
BAMBU_INVENTORY_LOCATIONS = [
    ("Bambu Studio Beta", Path.home()/"Library"/"Application Support"/"BambuStudioBeta"/"filament_inventory"/"spools.json"),
    ("Bambu Studio", Path.home()/"Library"/"Application Support"/"BambuStudio"/"filament_inventory"/"spools.json"),
]
if os.name == "nt" and os.environ.get("APPDATA"):
    BAMBU_STUDIO_CATALOG_LOCATIONS = [
        Path(os.environ.get("ProgramFiles",""))/"Bambu Studio"/"resources"/"profiles"/"BBL"/"filament"/"filaments_color_codes.json",
        Path(os.environ.get("ProgramFiles",""))/"BambuStudio"/"resources"/"profiles"/"BBL"/"filament"/"filaments_color_codes.json",
        Path(os.environ["APPDATA"])/"BambuStudio"/"system"/"BBL"/"filament"/"filaments_color_codes.json",
        Path(os.environ["APPDATA"])/"BambuStudioBeta"/"system"/"BBL"/"filament"/"filaments_color_codes.json",
        Path(os.environ["APPDATA"])/"OrcaSlicer"/"system"/"BBL"/"filament"/"filaments_color_codes.json",
    ]
    BAMBU_STUDIO_APP_LOCATIONS = [
        Path(os.environ.get("ProgramFiles",""))/"Bambu Studio",
        Path(os.environ.get("ProgramFiles",""))/"BambuStudio",
        Path(os.environ.get("ProgramFiles(x86)",""))/"Bambu Studio",
        Path(os.environ.get("ProgramFiles(x86)",""))/"BambuStudio",
    ]
    BAMBU_INVENTORY_LOCATIONS = [
        ("Bambu Studio Beta", Path(os.environ["APPDATA"])/"BambuStudioBeta"/"filament_inventory"/"spools.json"),
        ("Bambu Studio", Path(os.environ["APPDATA"])/"BambuStudio"/"filament_inventory"/"spools.json"),
    ]

def is_auto_quality_bias(value):
    return str(value).strip().lower() in ("auto","smart")

def clamp_quality_bias(value):
    try:
        return max(0,min(100,int(value)))
    except (TypeError,ValueError):
        raise RuntimeError("Quality versus waste must be 0-100, or auto for smart planning.")

def quality_mix_limit(quality_bias):
    quality_bias=clamp_quality_bias(quality_bias)
    if quality_bias <= DEFAULT_QUALITY_BIAS:
        return MAX_RELIABLE_MIX_DE
    span=100-DEFAULT_QUALITY_BIAS
    return MAX_RELIABLE_MIX_DE + (MAX_HIGH_QUALITY_MIX_DE-MAX_RELIABLE_MIX_DE) * ((quality_bias-DEFAULT_QUALITY_BIAS)/span)

def normalize_planner_mode(planner_mode):
    value=str(planner_mode or "best").strip().lower()
    if value not in PLANNER_MODES:
        raise RuntimeError(f"Unknown planner mode {planner_mode!r}. Choose best or fast.")
    return value

def normalize_planning_sample(planning_sample):
    value=str(planning_sample or "paint").strip().lower()
    aliases={
        "paint-states":"paint",
        "paint_states":"paint",
        "source":"paint",
        "render":"preview",
        "preview-mesh":"preview",
        "preview_mesh":"preview",
    }
    value=aliases.get(value,value)
    if value not in PLANNING_SAMPLES:
        raise RuntimeError(f"Unknown planning sample {planning_sample!r}. Choose paint or preview.")
    return value

def planner_is_best(planner_mode):
    return normalize_planner_mode(planner_mode) == "best"

def high_fidelity_quality(quality_bias, planner_mode="best"):
    return planner_is_best(planner_mode) and clamp_quality_bias(quality_bias) >= HIGH_FIDELITY_QUALITY

def anchor_pool_limit_for_quality(quality_bias, planner_mode="best"):
    return HIGH_FIDELITY_ANCHOR_POOL_LIMIT if high_fidelity_quality(quality_bias, planner_mode) else ANCHOR_POOL_LIMIT

def anchor_beam_width_for_quality(quality_bias, planner_mode="best"):
    return HIGH_FIDELITY_ANCHOR_BEAM_WIDTH if high_fidelity_quality(quality_bias, planner_mode) else ANCHOR_BEAM_WIDTH

def maximum_requested_slots_for_mode(mode):
    return min(MAX_REAL_SLOTS, len(CMYK_TARGETS)) if mode=="cmykw" else MAX_REAL_SLOTS

def automatic_slot_counts_for_mode(mode):
    upper=min(DEFAULT_AUTO_MAX_REAL_SLOTS, maximum_requested_slots_for_mode(mode))
    minimum=4 if mode=="cmykw" else MIN_REAL_SLOTS
    return list(range(minimum, upper+1))

def catalog_region_label(region):
    key=str(region or "global").strip().lower()
    if key not in CATALOG_REGIONS:
        raise RuntimeError("Unknown catalog region. Choose one of: " + ", ".join(CATALOG_REGIONS))
    return CATALOG_REGIONS[key]

def hx(c):
    c=str(c).strip()
    c=c if c.startswith("#") else "#"+c
    return c[:7].upper() if re.match(r"^#[0-9A-Fa-f]{6}", c) else c
def rgb(h):
    h=hx(h); return tuple(int(h[i:i+2],16) for i in (1,3,5))
def tohex(r,g,b):
    return "#{:02X}{:02X}{:02X}".format(max(0,min(255,int(round(r)))),max(0,min(255,int(round(g)))),max(0,min(255,int(round(b)))))
def to_linear(c):
    c/=255.0
    return c/12.92 if c<=0.04045 else ((c+0.055)/1.055)**2.4
def rgb_to_lab(r,g,b):
    rl,gl,bl=to_linear(r),to_linear(g),to_linear(b)
    X=rl*0.4124564+gl*0.3575761+bl*0.1804375
    Y=rl*0.2126729+gl*0.7151522+bl*0.0721750
    Z=rl*0.0193339+gl*0.1191920+bl*0.9503041
    Xn,Yn,Zn=0.95047,1.0,1.08883
    def f(t): return t**(1/3) if t>0.008856 else 7.787*t+16/116
    return 116*f(Y/Yn)-16,500*(f(X/Xn)-f(Y/Yn)),200*(f(Y/Yn)-f(Z/Zn))
def lab_to_rgb(L,a,b):
    fy=(L+16)/116
    fx=fy+a/500
    fz=fy-b/200
    def finv(t):
        cube=t**3
        return cube if cube>0.008856 else (t-16/116)/7.787
    X,Y,Z=0.95047*finv(fx),finv(fy),1.08883*finv(fz)
    rl=X*3.2404542+Y*-1.5371385+Z*-0.4985314
    gl=X*-0.9692660+Y*1.8760108+Z*0.0415560
    bl=X*0.0556434+Y*-0.2040259+Z*1.0572252
    def encode(channel):
        channel=max(0.0,min(1.0,channel))
        out=12.92*channel if channel<=0.0031308 else 1.055*(channel**(1/2.4))-0.055
        return out*255
    return encode(rl),encode(gl),encode(bl)
def delta_e_2000(lab1, lab2):
    """CIEDE2000 perceptual difference, using the standard graphic-arts weights."""
    L1,a1,b1=lab1; L2,a2,b2=lab2
    c1=math.hypot(a1,b1); c2=math.hypot(a2,b2)
    c_bar=(c1+c2)/2
    g=0.5*(1-math.sqrt((c_bar**7)/(c_bar**7+25**7))) if c_bar else 0.5
    ap1=(1+g)*a1; ap2=(1+g)*a2
    cp1=math.hypot(ap1,b1); cp2=math.hypot(ap2,b2)
    hp1=(math.degrees(math.atan2(b1,ap1))+360)%360 if cp1 else 0
    hp2=(math.degrees(math.atan2(b2,ap2))+360)%360 if cp2 else 0
    dL=L2-L1
    dC=cp2-cp1
    if cp1*cp2 == 0:
        dh=0
    elif abs(hp2-hp1)<=180:
        dh=hp2-hp1
    elif hp2<=hp1:
        dh=hp2-hp1+360
    else:
        dh=hp2-hp1-360
    dH=2*math.sqrt(cp1*cp2)*math.sin(math.radians(dh/2))
    lp=(L1+L2)/2
    cp=(cp1+cp2)/2
    if cp1*cp2 == 0:
        hp=hp1+hp2
    elif abs(hp1-hp2)<=180:
        hp=(hp1+hp2)/2
    elif hp1+hp2<360:
        hp=(hp1+hp2+360)/2
    else:
        hp=(hp1+hp2-360)/2
    t=(1 - 0.17*math.cos(math.radians(hp-30))
       + 0.24*math.cos(math.radians(2*hp))
       + 0.32*math.cos(math.radians(3*hp+6))
       - 0.20*math.cos(math.radians(4*hp-63)))
    sl=1+(0.015*(lp-50)**2)/math.sqrt(20+(lp-50)**2)
    sc=1+0.045*cp
    sh=1+0.015*cp*t
    rt=-2*math.sqrt((cp**7)/(cp**7+25**7))*math.sin(
        math.radians(60*math.exp(-((hp-275)/25)**2))
    ) if cp else 0
    return math.sqrt((dL/sl)**2+(dC/sc)**2+(dH/sh)**2+rt*(dC/sc)*(dH/sh))
@lru_cache(maxsize=65536)
def lab_for_hex(color):
    return rgb_to_lab(*rgb(color))

@lru_cache(maxsize=DIST_CACHE_SIZE)
def cached_dist(a,b):
    return delta_e_2000(lab_for_hex(a), lab_for_hex(b))

def dist(a,b):
    return cached_dist(hx(a), hx(b))
def luminance(h):
    r,g,b=rgb(h); return .2126*r+.7152*g+.0722*b
def serialized_ratio_text(ratios):
    return ",".join(f"{float(value):.4f}" for value in ratios)

def bambu_ratio_weights(ratios):
    text=ratios if isinstance(ratios,str) else serialized_ratio_text(ratios)
    # Bambu Studio serializes normalized ratios to four decimals, then loads
    # them as integer percentages before computing the mixed swatch.
    output=[]
    for value in text.split(","):
        if not value.strip():
            continue
        parsed=struct.unpack("<f",struct.pack("<f",float(value)))[0]
        rounded=struct.unpack("<f",struct.pack("<f",parsed*100.0+0.5))[0]
        output.append(int(rounded))
    return output

@lru_cache(maxsize=MIX_CACHE_SIZE)
def cached_bambu_mix(hexes, weights):
    return bambu_blend_color_multi(hexes,weights)

def mix(hexes, ratios, model="bambu"):
    """Return the exact swatch Bambu Studio reconstructs for a mixed recipe."""
    weights=tuple(bambu_ratio_weights(ratios))
    return cached_bambu_mix(tuple(hx(color) for color in hexes),weights)

def normalized_ratios(ratios):
    return tuple(round(float(value),4) for value in ratios)

def ratio_family(name):
    if name=="none":
        return ()
    if name=="half2":
        return ((0.5,0.5),)
    if name=="standard2":
        return tuple(normalized_ratios(ratio) for ratio in R2)
    if name=="fine2":
        return tuple(normalized_ratios(ratio) for ratio in R2_FINE)
    if name=="standard3":
        return tuple(normalized_ratios(ratio) for ratio in R3)
    if name=="fine3":
        return tuple(normalized_ratios(ratio) for ratio in R3_FINE)
    raise RuntimeError(f"Unknown mix ratio family: {name}")

def score_pair_family(quality_bias, planner_mode):
    return "standard2" if high_fidelity_quality(quality_bias,planner_mode) else "half2"

def score_triple_family(quality_bias, planner_mode):
    return "none"

@lru_cache(maxsize=MIX_RECIPE_INDEX_CACHE_SIZE)
def mix_recipe_index_for_signature(signature, mix_model="bambu",
                                   pair_family="standard2", triple_family="none"):
    colors=tuple(hx(color) for color in signature)
    recipes=[]
    for i,j in combinations(range(len(colors)),2):
        component_colors=(colors[i],colors[j])
        for ratios in ratio_family(pair_family):
            recipes.append(((i+1,j+1),ratios,mix(component_colors,ratios,mix_model)))
    if triple_family!="none" and len(colors)>=3:
        for combo in combinations(range(len(colors)),3):
            component_colors=(colors[combo[0]],colors[combo[1]],colors[combo[2]])
            component_slots=(combo[0]+1,combo[1]+1,combo[2]+1)
            for ratios in ratio_family(triple_family):
                recipes.append((component_slots,ratios,mix(component_colors,ratios,mix_model)))
    return tuple(recipes)

def mix_recipe_index(anchors, mix_model="bambu", pair_family="standard2", triple_family="none"):
    return mix_recipe_index_for_signature(anchor_signature(anchors),mix_model,pair_family,triple_family)

# Target-aware in-memory recipe database for anchor search. The output 3MF can
# hold up to 32 paint slots, but the hard part is choosing the physical anchors:
# thousands of trial anchor sets would otherwise recompute the same Bambu
# pair/triple halftone recipes for every source color. This cache builds the
# reusable candidate mix errors once for the active Bambu pool and lets the
# beam search test anchor sets with cheap set-membership checks.
@lru_cache(maxsize=ANCHOR_SCORE_HINT_CACHE_SIZE)
def anchor_score_hint_database(pool_signature, target_signature, mix_model,
                               pair_family, triple_family, mix_limit):
    pool_colors=tuple(hx(color) for color in pool_signature)
    target_colors=tuple(hx(color) for color in target_signature)
    mix_limit=float(mix_limit)
    pair_ratios=ratio_family(pair_family)
    triple_ratios=ratio_family(triple_family)
    hints_by_target=[]
    for target in target_colors:
        hints=[]
        for i,j in combinations(range(len(pool_colors)),2):
            component_colors=(pool_colors[i],pool_colors[j])
            best_error=min(
                dist(target,mix(component_colors,ratios,mix_model))
                for ratios in pair_ratios
            )
            if best_error<=mix_limit:
                hints.append(((pool_colors[i],pool_colors[j]),best_error))
        if triple_ratios and len(pool_colors)>=3:
            nearby=sorted(
                range(len(pool_colors)),
                key=lambda index:dist(target,pool_colors[index])
            )[:min(ANCHOR_SCORE_TRIPLE_NEIGHBORS,len(pool_colors))]
            for combo in combinations(nearby,3):
                component_colors=(pool_colors[combo[0]],pool_colors[combo[1]],pool_colors[combo[2]])
                best_error=min(
                    dist(target,mix(component_colors,ratios,mix_model))
                    for ratios in triple_ratios
                )
                if best_error<=mix_limit:
                    hints.append((component_colors,best_error))
        hints.sort(key=lambda item:item[1])
        hints_by_target.append(tuple(hints[:ANCHOR_SCORE_HINTS_PER_TARGET]))
    return tuple(hints_by_target)

def choose_file():
    try:
        s='POSIX path of (choose file with prompt "Choose a .3mf file" of type {"3mf"})'
        return Path(subprocess.check_output(["osascript","-e",s], text=True).strip())
    except Exception:
        return None

def find_project_settings(names):
    for n in names:
        if n.lower().endswith("metadata/project_settings.config"):
            return n
    for n in names:
        if n.lower().endswith("project_settings.config"):
            return n
    return None

def read_json_config(path):
    try:
        obj,_=json.JSONDecoder().raw_decode(path.read_text(errors="replace").lstrip())
        return obj
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Could not parse {path.name}: line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc

def validated_archive_infos(archive):
    infos=archive.infolist()
    if len(infos)>MAX_ARCHIVE_ENTRIES:
        raise RuntimeError("3MF archive contains too many entries")
    total=sum(info.file_size for info in infos)
    if total>MAX_ARCHIVE_UNCOMPRESSED_BYTES:
        raise RuntimeError("3MF archive is larger than the safe processing limit")
    seen=set()
    for info in infos:
        normalized=info.filename.replace("\\","/")
        lower=normalized.lower()
        if lower in seen:
            raise RuntimeError(f"Duplicate path in 3MF archive: {info.filename}")
        seen.add(lower)
        relative=Path(normalized)
        mode=(info.external_attr >> 16) & 0o170000
        if relative.is_absolute() or ".." in relative.parts or re.match(r"^[A-Za-z]:",normalized) or mode == 0o120000:
            raise RuntimeError(f"Unsafe path in 3MF archive: {info.filename}")
    return infos

def safe_extract_archive(archive, destination):
    infos=validated_archive_infos(archive)
    base=destination.resolve()
    for info in infos:
        relative=Path(info.filename.replace("\\","/"))
        target=(destination/relative).resolve()
        if target != base and base not in target.parents:
            raise RuntimeError(f"Unsafe path in 3MF archive: {info.filename}")
        if info.is_dir():
            target.mkdir(parents=True,exist_ok=True)
            continue
        target.parent.mkdir(parents=True,exist_ok=True)
        with archive.open(info) as source, target.open("wb") as output:
            shutil.copyfileobj(source,output,1024*1024)

def stream_digest(source, normalize_paint=False):
    digest=hashlib.sha256()
    while True:
        block=source.readline() if normalize_paint else source.read(1024*1024)
        if not block:
            break
        if normalize_paint:
            block=PAINT_BYTES_VALUE_PATTERN.sub(lambda m: m.group(1)+m.group(2)+m.group(2),block)
        digest.update(block)
    return digest.hexdigest()

def preservation_snapshot(directory, settings_relative):
    snapshot={}
    model_settings="metadata/model_settings.config"
    for path in sorted(item for item in directory.rglob("*") if item.is_file()):
        relative=path.relative_to(directory).as_posix()
        lower=relative.lower()
        if lower == settings_relative.lower() or lower == model_settings:
            continue
        normalize=lower.startswith("3d/objects/") and lower.endswith(".model")
        with path.open("rb") as source:
            snapshot[relative]=("paint-only-model" if normalize else "unchanged",stream_digest(source,normalize))
    return snapshot

def verify_preservation(archive, snapshot):
    names=set(archive.namelist())
    for relative,(kind,expected) in snapshot.items():
        if relative not in names:
            raise RuntimeError(f"Output dropped source member {relative}")
        with archive.open(relative) as source:
            actual=stream_digest(source,kind=="paint-only-model")
        if actual != expected:
            message="geometry or UV data changed" if kind=="paint-only-model" else "source resource changed"
            raise RuntimeError(f"Output {message}: {relative}")
    return {
        "geometryPreserved":True,
        "textureResourcesPreserved":True,
        "checkedMembers":len(snapshot),
    }

def colors_from_project(obj):
    v=obj.get("filament_colour",[])
    if not isinstance(v,list):
        return []
    out=[]
    for slot,value in enumerate(v,start=1):
        raw=str(value).strip()
        if not re.fullmatch(r"#?[0-9A-Fa-f]{6}(?:[0-9A-Fa-f]{2})?",raw):
            raise RuntimeError(f"filament_colour slot {slot} has invalid color {value!r}")
        out.append(hx(raw).upper())
    return out

def preview_colors_from_project(obj, mix_model="bambu"):
    colors=colors_from_project(obj)
    mixed=obj.get("filament_is_mixed",[])
    components=obj.get("filament_mixed_components",[])
    ratios=obj.get("filament_mixed_sublayer_ratios",[])
    for index in range(min(len(colors),len(mixed),len(components),len(ratios))):
        if mixed[index]!="1":
            continue
        try:
            slots=[int(value) for value in components[index].split(",") if value.strip()]
            ratio_text=ratios[index]
            weights=bambu_ratio_weights(ratio_text)
            if len(slots)==len(weights) and slots and all(1<=slot<=len(colors) for slot in slots):
                colors[index]=mix([colors[slot-1] for slot in slots],ratio_text,mix_model)
        except ValueError:
            continue
    return colors

def profile_for_anchor(name):
    families=sorted(PROFILE_BY_FAMILY,key=len,reverse=True)
    for family in families:
        if name.startswith(family):
            return PROFILE_BY_FAMILY[family]
    return PROFILE_BY_FAMILY["PLA Basic"]

def filament_family(name):
    families=sorted(PROFILE_BY_FAMILY,key=len,reverse=True)
    return next((family for family in families if name == family or name.startswith(f"{family} ")), "PLA Basic")

def supported_catalog_family(series, scope):
    series=str(series or "").strip()
    if not (series == "PLA-CF" or series.startswith("PLA ")):
        return False
    if series.startswith("PLA Support") or series in {"PLA Support", "PLA PVA"}:
        return False
    core={"PLA Basic","PLA Matte","PLA Silk+"}
    return series in core if scope=="core" else series in PROFILE_BY_FAMILY

def bambu_catalog_color_name(row):
    names=row.get("fila_color_name") if isinstance(row,dict) else None
    if isinstance(names,dict):
        return str(names.get("en") or next((value for value in names.values() if value), "")).strip()
    return str(names or "").strip()

def bambu_catalog_hexes(row):
    colors=row.get("fila_color") if isinstance(row,dict) else None
    if not isinstance(colors,list):
        return []
    return [hx(color) for color in colors if re.match(r"^#[0-9A-Fa-f]{6}", hx(color))]

@lru_cache(maxsize=1)
def bambu_studio_catalog_rows():
    for path in BAMBU_STUDIO_CATALOG_LOCATIONS:
        if not path or not path.exists():
            continue
        try:
            payload=json.loads(path.read_text(errors="replace"))
        except (OSError, json.JSONDecodeError):
            continue
        rows=payload.get("data",payload if isinstance(payload,list) else [])
        if isinstance(rows,list) and rows:
            return str(path), rows
    return None, []

@lru_cache(maxsize=1)
def installed_bambu_studio_version():
    for app in BAMBU_STUDIO_APP_LOCATIONS:
        plist_path=app/"Contents"/"Info.plist"
        if not plist_path.exists():
            continue
        try:
            with plist_path.open("rb") as handle:
                payload=plistlib.load(handle)
            version=str(payload.get("CFBundleShortVersionString") or "").strip()
            build=str(payload.get("CFBundleVersion") or "").strip()
            if version or build:
                return {"version":version or None,"build":build or None,"path":str(app)}
        except (OSError, plistlib.InvalidFileException, ValueError):
            continue
    return {"version":None,"build":None,"path":None}

@lru_cache(maxsize=1)
def catalog_summary():
    source,rows=bambu_studio_catalog_rows()
    rows=rows or fallback_bambu_catalog_rows()
    all_palette=catalog_palette("all")
    core_palette=catalog_palette("core")
    family_counts=Counter(item["series"] for item in all_palette)
    return {
        "source":source or "built-in fallback",
        "bambuStudio":installed_bambu_studio_version(),
        "totalRows":len(rows),
        "coreUsableCount":len(core_palette),
        "allUsableCount":len(all_palette),
        "families":[
            {"series":series,"count":count}
            for series,count in sorted(family_counts.items(), key=lambda item:(-item[1], item[0]))
        ],
    }

def fallback_bambu_catalog_rows():
    rows=[]
    for name,color in BAMBU_PLA:
        series=filament_family(name)
        color_name=name.removeprefix(series).strip() or series
        _,filament_id=profile_for_anchor(series)
        rows.append({
            "fila_id":filament_id,
            "fila_type":series,
            "fila_color_name":{"en":color_name},
            "color_code":"",
            "fila_color":[hx(color)],
            "fallback":True,
        })
    return rows

@lru_cache(maxsize=1)
def installed_bambu_color_names():
    names={}
    _,rows=bambu_studio_catalog_rows()
    for row in rows or fallback_bambu_catalog_rows():
        if not isinstance(row,dict):
            continue
        series=str(row.get("fila_type") or "").strip()
        english=bambu_catalog_color_name(row)
        if not series or not english:
            continue
        for color in bambu_catalog_hexes(row):
            names.setdefault((series,color),f"{series} {english}")
    return names

def official_filament_name(series, color):
    normalized=hx(color)
    installed=installed_bambu_color_names().get((series,normalized))
    if installed:
        return installed
    return next(
        (name for name,candidate in BAMBU_PLA if filament_family(name)==series and hx(candidate)==normalized),
        f"{series} {normalized}",
    )

def read_bambu_inventory(required=True, minimum_colors=MIN_REAL_SLOTS):
    catalog_info=catalog_summary()
    inventory_match=next(((label,path) for label,path in BAMBU_INVENTORY_LOCATIONS if path.exists()),None)
    inventory_label,inventory_path=inventory_match if inventory_match else (None,None)
    if inventory_path is None:
        if required:
            raise RuntimeError("Bambu Studio filament inventory was not found. Enable Inventory Beta and add active PLA spools.")
        catalog_options=catalog_palette("all")
        return {
            "source":None,
            "allCount":0,
            "usableCount":0,
            "totalGrams":0.0,
            "catalog":catalog_info,
            "anchorOptions":[anchor_option_payload(item) for item in catalog_options],
            "spools":[],
        }
    payload=json.loads(inventory_path.read_text(errors="replace"))
    raw_spools=payload.get("spools",[]) if isinstance(payload,dict) else []
    spools=[]
    for raw in raw_spools:
        if not isinstance(raw,dict):
            continue
        material=str(raw.get("material_type","")).strip()
        status=str(raw.get("status","active")).strip().lower()
        remaining=float(raw.get("net_weight") or 0)
        color=hx(raw.get("color_code") or (raw.get("colors") or [""])[0])
        if material != "PLA" or status != "active" or remaining <= 0 or not re.match(r"^#[0-9A-F]{6}$",color):
            continue
        series=str(raw.get("series") or "PLA Basic").strip()
        setting_id=str(raw.get("setting_id") or profile_for_anchor(series)[1]).strip()
        color_name=str(raw.get("color_name") or "").strip()
        display_name=f"{series} {color_name}".strip() if color_name else official_filament_name(series,color)
        spools.append({
            "name":display_name,
            "series":series,
            "brand":str(raw.get("brand") or "Bambu Lab"),
            "color":color,
            "preset":f"Bambu {series} @BBL H2C 0.2 nozzle",
            "filamentID":setting_id,
            "remainingGrams":round(remaining,1),
            "initialGrams":round(float(raw.get("initial_weight") or remaining),1),
        })
    spools.sort(key=lambda item:(item["series"],item["color"],-item["remainingGrams"]))
    if len({spool["color"] for spool in spools}) < minimum_colors:
        raise RuntimeError(f"Bambu Studio inventory needs at least {minimum_colors} distinct active PLA colors with remaining material.")
    return {
        "source":f"{inventory_label} local inventory",
        "allCount":len(raw_spools),
        "usableCount":len(spools),
        "totalGrams":round(sum(item["remainingGrams"] for item in spools),1),
        "catalog":catalog_info,
        "anchorOptions":[anchor_option_payload(item) for item in catalog_palette("all",{"spools":spools})],
        "spools":spools,
    }

def inventory_palette(inventory):
    by_series_color={}
    for spool in inventory["spools"]:
        key=(spool["series"],spool["color"])
        if key not in by_series_color:
            by_series_color[key]=dict(spool)
        else:
            by_series_color[key]["remainingGrams"]+=spool["remainingGrams"]
    by_color={}
    for spool in by_series_color.values():
        current=by_color.get(spool["color"])
        if current is None or spool["remainingGrams"] > current["remainingGrams"]:
            by_color[spool["color"]]=spool
    return list(by_color.values())

def catalog_palette(scope="core", inventory=None, material_families=None):
    material_families=normalize_material_families(material_families)
    options=[]
    catalog_source,rows=bambu_studio_catalog_rows()
    rows=rows or fallback_bambu_catalog_rows()
    seen=set()
    for row in rows:
        if not isinstance(row,dict):
            continue
        series=str(row.get("fila_type") or "").strip()
        if not supported_catalog_family(series,scope):
            continue
        if material_families and series not in material_families:
            continue
        colors=bambu_catalog_hexes(row)
        if len(colors) != 1:
            continue
        color=colors[0]
        color_name=bambu_catalog_color_name(row)
        if not color_name:
            continue
        key=(series,color)
        if key in seen:
            continue
        seen.add(key)
        preset,default_filament_id=profile_for_anchor(series)
        filament_id=str(row.get("fila_id") or default_filament_id)
        color_code=str(row.get("color_code") or row.get("fila_color_code") or "")
        name=f"{series} {color_name}"
        options.append({
            "name":name,
            "series":series,
            "brand":"Bambu Lab",
            "color":color,
            "preset":preset,
            "filamentID":filament_id,
            "remainingGrams":None,
            "initialGrams":None,
            "availability":"confirm-regionally",
            "bambuColorCode":color_code,
            "catalogSource":catalog_source or "built-in fallback",
        })
    if scope=="all" and inventory:
        existing={(item["series"],item["color"]) for item in options}
        for spool in inventory.get("spools",[]):
            key=(spool["series"],spool["color"])
            if material_families and spool["series"] not in material_families:
                continue
            if key not in existing and spool.get("brand","").lower().startswith("bambu"):
                option=dict(spool)
                option["availability"]="local-inventory"
                options.append(option)
                existing.add(key)
    return options

def custom_palette(path):
    if not path:
        raise RuntimeError("Custom brands source requires a palette JSON file.")
    palette_path=Path(path).expanduser()
    try:
        payload=json.loads(palette_path.read_text(errors="replace"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"Custom palette file was not found: {palette_path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Custom palette JSON could not be parsed at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc
    items=payload.get("filaments",payload) if isinstance(payload,dict) else payload
    if not isinstance(items,list):
        raise RuntimeError("Custom palette must contain a JSON list or a filaments list.")
    options=[]
    for item in items:
        if not isinstance(item,dict) or not re.match(r"^#[0-9A-Fa-f]{6}$",hx(item.get("color",""))):
            continue
        family=str(item.get("series") or "PLA Basic")
        preset,filament_id=profile_for_anchor(family)
        try:
            remaining=float(item["remainingGrams"]) if item.get("remainingGrams") is not None else None
            initial=float(item["initialGrams"]) if item.get("initialGrams") is not None else remaining
        except (TypeError,ValueError):
            remaining=initial=None
        options.append({
            "name":str(item.get("name") or family),
            "series":family,
            "brand":str(item.get("brand") or "Custom"),
            "color":hx(item["color"]),
            "preset":str(item.get("preset") or preset),
            "filamentID":str(item.get("filamentID") or filament_id),
            "remainingGrams":remaining,
            "initialGrams":initial,
            "availability":"user-supplied",
        })
    if len({item["color"] for item in options}) < MIN_REAL_SLOTS:
        raise RuntimeError("Custom palette needs at least two distinct valid colors.")
    return options

def exact_cmykw_palette():
    preset,filament_id=PROFILE_BY_FAMILY["PLA Basic"]
    return [
        {
            "name":f"Exact {role}",
            "series":"CMYKW",
            "brand":"User supplied",
            "color":hx(color),
            "preset":preset,
            "filamentID":filament_id,
            "remainingGrams":None,
            "initialGrams":None,
            "role":role,
        }
        for role,color in CMYK_TARGETS
    ]

def glb_texture(reference, destination):
    with reference.open("rb") as source:
        header=source.read(12)
        if len(header)!=12 or header[:4]!=b"glTF":
            raise RuntimeError("Reference GLB header is invalid")
        _,version,total=struct.unpack("<4sII",header)
        if version != 2 or total > MAX_REFERENCE_BYTES:
            raise RuntimeError("Reference GLB is unsupported or larger than the safe limit")
        json_length,json_type=struct.unpack("<II",source.read(8))
        if json_type != 0x4E4F534A or json_length > 16*1024*1024:
            raise RuntimeError("Reference GLB has no usable JSON chunk")
        document=json.loads(source.read(json_length).decode("utf-8"))
        bin_length,bin_type=struct.unpack("<II",source.read(8))
        if bin_type != 0x004E4942:
            raise RuntimeError("Reference GLB has no embedded binary texture")
        bin_start=source.tell()
        images=document.get("images") or []
        views=document.get("bufferViews") or []
        image=next((item for item in images if "bufferView" in item),None)
        if image is None:
            return None
        view=views[int(image["bufferView"])]
        length=int(view.get("byteLength",0))
        offset=int(view.get("byteOffset",0))
        if length<=0 or length>100*1024*1024 or offset+length>bin_length:
            raise RuntimeError("Reference GLB embedded texture is invalid")
        mime=image.get("mimeType","image/png")
        extension=".jpg" if "jpeg" in mime else ".png"
        output=destination/f"reference_texture{extension}"
        source.seek(bin_start+offset)
        output.write_bytes(source.read(length))
        return output

def obj_texture(reference):
    try:
        source=reference.read_text(errors="replace")
        material=next((line.split(None,1)[1].strip() for line in source.splitlines()
                       if line.lower().startswith("mtllib ")),None)
        if not material:
            return None
        mtl=(reference.parent/material).resolve()
        if not mtl.is_file():
            return None
        texture=next((line.split(None,1)[1].strip() for line in mtl.read_text(errors="replace").splitlines()
                      if line.lower().startswith("map_kd ")),None)
        image=(mtl.parent/texture).resolve() if texture else None
        return image if image and image.is_file() else None
    except (OSError,IndexError):
        return None

def sample_reference_colors(image, destination):
    if image is None:
        return []
    try:
        from PIL import Image
        with Image.open(image) as source:
            resized=source.convert("RGB").resize((96,96))
            pixel_data=(resized.get_flattened_data() if hasattr(resized,"get_flattened_data")
                        else resized.getdata())
            pixels=list(pixel_data)
    except ImportError:
        bmp=destination/"reference_sample.bmp"
        if not Path("/usr/bin/sips").exists():
            return []
        result=subprocess.run(["/usr/bin/sips","-Z","512","-s","format","bmp",str(image),"--out",str(bmp)],
                              capture_output=True,text=True)
        if result.returncode or not bmp.exists():
            return []
        data=bmp.read_bytes()
        offset=struct.unpack_from("<I",data,10)[0]
        width=struct.unpack_from("<i",data,18)[0]
        height=abs(struct.unpack_from("<i",data,22)[0])
        bits=struct.unpack_from("<H",data,28)[0]
        if bits not in (24,32) or width<=0 or height<=0:
            return []
        stride=((width*(bits//8)+3)//4)*4
        step=max(1,min(width,height)//96)
        pixels=[]
        for row in range(0,height,step):
            start=offset+row*stride
            for col in range(0,width,step):
                blue,green,red=data[start+col*(bits//8):start+col*(bits//8)+3]
                pixels.append((red,green,blue))
    counts=Counter((red//32,green//32,blue//32) for red,green,blue in pixels)
    total=sum(counts.values()) or 1
    return [{"color":tohex(red*32+16,green*32+16,blue*32+16),"weight":round(count/total,4)}
            for (red,green,blue),count in counts.most_common(8)]

def load_image_pixels(image, destination):
    if image.stat().st_size > MAX_REFERENCE_BYTES:
        raise RuntimeError("Texture exceeds the safe import size limit")
    try:
        from PIL import Image
        with Image.open(image) as source:
            normalized=source.convert("RGB")
            normalized.thumbnail((2048,2048))
            return normalized.width, normalized.height, normalized.tobytes()
    except ImportError:
        bmp=destination/"import_texture.bmp"
        result=subprocess.run(["/usr/bin/sips","-Z","2048","-s","format","bmp",str(image),"--out",str(bmp)],
                              capture_output=True,text=True) if Path("/usr/bin/sips").exists() else None
        if not result or result.returncode or not bmp.exists():
            raise RuntimeError("Textured import needs Pillow, or macOS image conversion support")
        data=bmp.read_bytes()
        offset=struct.unpack_from("<I",data,10)[0]
        width=struct.unpack_from("<i",data,18)[0]
        raw_height=struct.unpack_from("<i",data,22)[0]
        height=abs(raw_height)
        bits=struct.unpack_from("<H",data,28)[0]
        if bits not in (24,32) or width<=0 or height<=0:
            raise RuntimeError("Texture could not be read for OBJ import")
        stride=((width*(bits//8)+3)//4)*4
        pixels=bytearray()
        rows=range(height-1,-1,-1) if raw_height>0 else range(height)
        for row in rows:
            start=offset+row*stride
            for column in range(width):
                blue,green,red=data[start+column*(bits//8):start+column*(bits//8)+3]
                pixels.extend((red,green,blue))
        return width,height,bytes(pixels)

def texture_pixel(texture, u, v):
    width,height,pixels=texture
    x=min(width-1,max(0,int((u%1.0)*(width-1))))
    y=min(height-1,max(0,int((1-(v%1.0))*(height-1))))
    offset=(y*width+x)*3
    return tohex(pixels[offset],pixels[offset+1],pixels[offset+2])

def quantized_texture_color(color, step=8):
    return tohex(*(min(255,(channel//step)*step+step//2) for channel in rgb(color)))

def kmeans_colors(colors, limit, iterations=10):
    counts=Counter(colors)
    unique=list(counts)
    if len(unique)<=limit:
        palette=sorted(unique,key=lambda c:(-counts[c],c))
    else:
        weighted=sorted(unique,key=lambda c:(-counts[c],c))
        centers=[rgb_to_lab(*rgb(weighted[0]))]
        while len(centers)<limit:
            candidate=max(weighted,key=lambda c:min(delta_e_2000(rgb_to_lab(*rgb(c)),center)
                                                     for center in centers)*counts[c])
            centers.append(rgb_to_lab(*rgb(candidate)))
        for _ in range(iterations):
            groups=[[] for _ in centers]
            for color,count in counts.items():
                lab=rgb_to_lab(*rgb(color))
                index=min(range(len(centers)),key=lambda i:delta_e_2000(lab,centers[i]))
                groups[index].append((lab,count))
            new=[]
            for center,items in zip(centers,groups):
                total=sum(count for _,count in items)
                new.append(tuple(sum(lab[axis]*count for lab,count in items)/total for axis in range(3))
                           if total else center)
            if new==centers:
                break
            centers=new
        palette=[tohex(*lab_to_rgb(*center)) for center in centers]
    assignment={color:min(range(len(palette)),key=lambda i:dist(color,palette[i]))+1 for color in counts}
    return palette,assignment

def obj_geometry(source):
    positions=[]; texture_coordinates=[]; triangles=[]; missing_uv=0
    with source.open("r",errors="replace") as handle:
        for line in handle:
            values=line.strip().split()
            if not values:
                continue
            if values[0]=="v" and len(values)>=4:
                positions.append(tuple(float(value) for value in values[1:4]))
            elif values[0]=="vt" and len(values)>=3:
                texture_coordinates.append((float(values[1]),float(values[2])))
            elif values[0]=="f" and len(values)>=4:
                corners=[]
                for token in values[1:]:
                    indices=token.split("/")
                    vertex=int(indices[0])
                    vertex=vertex-1 if vertex>0 else len(positions)+vertex
                    uv=None
                    if len(indices)>1 and indices[1]:
                        coord=int(indices[1])
                        uv=coord-1 if coord>0 else len(texture_coordinates)+coord
                    if not (0<=vertex<len(positions)):
                        raise RuntimeError("OBJ face references a missing vertex")
                    if uv is None or not (0<=uv<len(texture_coordinates)):
                        missing_uv+=1
                        uv=None
                    corners.append((vertex,uv))
                for index in range(1,len(corners)-1):
                    triangles.append((corners[0],corners[index],corners[index+1]))
                    if len(triangles)>MAX_IMPORT_FACES:
                        raise RuntimeError("OBJ exceeds the import face safety limit")
    if not positions or not triangles:
        raise RuntimeError("OBJ import found no printable triangle mesh")
    return positions,texture_coordinates,triangles,missing_uv

def paint_code_for_slot(slot):
    return "".join(HEX_DIGITS[nibble] for nibble in reversed(encode_paint_state(slot)))

def basic_project_settings(colors):
    count=len(colors)
    matrix=["0" if row==column else "120" for row in range(count) for column in range(count)]
    return {
        "filament_colour":colors,
        "filament_settings_id":[MIXED_PROFILE_ID]*count,
        "filament_ids":[MIXED_FILAMENT_ID]*count,
        "filament_is_mixed":["0"]*count,
        "filament_mixed_components":[""]*count,
        "filament_mixed_sublayer_ratios":[""]*count,
        "filament_multi_colour":colors[:],
        "default_filament_colour":[""]*count,
        "filament_type":["PLA"]*count,
        "filament_vendor":["Bambu Lab"]*count,
        "flush_volumes_matrix":matrix,
    }

def import_obj_project(source, destination, temp_directory, texture_override=None, internal_colors=48, progress=None):
    texture=Path(texture_override).expanduser().resolve() if texture_override else obj_texture(source)
    if texture is None or not texture.is_file():
        raise RuntimeError("OBJ import requires a readable material texture or an explicit texture image")
    if texture.suffix.lower() not in (".png",".jpg",".jpeg"):
        raise RuntimeError("OBJ import currently embeds PNG or JPEG textures; convert other texture formats first")
    positions,uvs,triangles,missing_uv=obj_geometry(source)
    if missing_uv:
        raise RuntimeError("OBJ import requires UV coordinates on every painted face")
    if progress:
        progress(0.07, f"Loading polygons: {len(triangles):,} textured triangles")
    pixel_data=load_image_pixels(texture,temp_directory)
    if progress:
        progress(0.08, "Sampling texture colors")
    sampled=[]
    for triangle in triangles:
        coords=[uvs[corner[1]] for corner in triangle]
        u=sum(point[0] for point in coords)/3; v=sum(point[1] for point in coords)/3
        sampled.append(quantized_texture_color(texture_pixel(pixel_data,u,v)))
    if progress:
        progress(0.09, "Clustering sampled colors into printable paint states")
    internal_limit=max(MAX_BAMBU_PAINT_SLOT,min(128,int(internal_colors)))
    analysis_palette,_=kmeans_colors(sampled,min(internal_limit,len(set(sampled))))
    palette,assignment=kmeans_colors(sampled,min(MAX_BAMBU_PAINT_SLOT,len(set(sampled))))
    if len(palette)<MIN_REAL_SLOTS:
        palette.append("#000000" if dist(palette[0],"#000000")>dist(palette[0],"#FFFFFF") else "#FFFFFF")
    texture_extension=texture.suffix.lower() if texture.suffix.lower() in (".png",".jpg",".jpeg") else ".png"
    if texture_extension==".jpeg":
        texture_extension=".jpg"
    texture_name="source_texture"+texture_extension
    object_model=temp_directory/"import_object_1.model"
    with object_model.open("w") as model:
        model.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        model.write('<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" xmlns:m="http://schemas.microsoft.com/3dmanufacturing/material/2015/02">\n')
        model.write('<resources>\n')
        model.write(f'<m:texture2d id="2" path="/3D/Textures/{texture_name}" contenttype="image/{texture_extension[1:]}" tilestyleu="wrap" tilestylev="wrap"/>\n')
        model.write('<m:texture2dgroup id="3" texid="2">\n')
        for triangle in triangles:
            for corner in triangle:
                u,v=uvs[corner[1]]
                model.write(f'<m:tex2coord u="{u:.7f}" v="{v:.7f}"/>\n')
        model.write('</m:texture2dgroup>\n<object id="1" type="model"><mesh><vertices>\n')
        for x,y,z in positions:
            model.write(f'<vertex x="{x:.7f}" y="{y:.7f}" z="{z:.7f}"/>\n')
        model.write('</vertices><triangles>\n')
        for index,(triangle,color) in enumerate(zip(triangles,sampled)):
            texture_index=index*3
            slot=assignment[color]
            model.write(
                f'<triangle v1="{triangle[0][0]}" v2="{triangle[1][0]}" v3="{triangle[2][0]}" '
                f'pid="3" p1="{texture_index}" p2="{texture_index+1}" p3="{texture_index+2}" '
                f'paint_color="{paint_code_for_slot(slot)}"/>\n'
            )
        model.write('</triangles></mesh></object>\n</resources><build><item objectid="1"/></build>\n</model>\n')
    content_types=('<?xml version="1.0" encoding="UTF-8"?>'
                   '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
                   '<Default Extension="config" ContentType="application/octet-stream"/>'
                   f'<Default Extension="{texture_extension[1:]}" ContentType="image/{texture_extension[1:]}"/>'
                   '</Types>')
    rels=('<?xml version="1.0" encoding="UTF-8"?>'
          '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
          '<Relationship Target="/3D/Objects/object_1.model" Id="rel-1" '
          'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>'
          '</Relationships>')
    destination.parent.mkdir(parents=True,exist_ok=True)
    if progress:
        progress(0.11, "Building imported painted project")
    with zipfile.ZipFile(destination,"w",zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml",content_types)
        archive.writestr("_rels/.rels",rels)
        archive.writestr("Metadata/project_settings.config",json.dumps(basic_project_settings(palette),indent=2))
        archive.write(object_model,"3D/Objects/object_1.model")
        archive.write(texture,f"3D/Textures/{texture_name}")
    return {
        "sourceType":"Textured OBJ",
        "texture":texture.name,
        "vertexCount":len(positions),
        "triangleCount":len(triangles),
        "internalColorCount":len(analysis_palette),
        "exportColorCount":len(palette),
        "compressedForBambu":len(analysis_palette)>len(palette),
        "textureSamplingMaxDimension":2048,
    }

def read_glb_document(source):
    with source.open("rb") as handle:
        header=handle.read(12)
        if len(header)!=12 or header[:4]!=b"glTF":
            raise RuntimeError("GLB import header is invalid")
        _,version,total=struct.unpack("<4sII",header)
        if version!=2 or total>MAX_REFERENCE_BYTES:
            raise RuntimeError("GLB import is unsupported or exceeds the safe size limit")
        json_length,json_type=struct.unpack("<II",handle.read(8))
        if json_type!=0x4E4F534A:
            raise RuntimeError("GLB import contains no JSON scene")
        document=json.loads(handle.read(json_length).decode("utf-8"))
        declared_faces=0
        for mesh in document.get("meshes",[]):
            for primitive in mesh.get("primitives",[]):
                if primitive.get("mode",4)!=4:
                    continue
                accessor_index=primitive.get("indices")
                if accessor_index is None:
                    accessor_index=primitive.get("attributes",{}).get("POSITION")
                if accessor_index is not None:
                    declared_faces+=int(document["accessors"][accessor_index].get("count",0))//3
        if declared_faces>MAX_IMPORT_FACES:
            raise RuntimeError(
                "GLB exceeds the 2,000,000-face import safety limit. Reduce the mesh first "
                "or use it as a visual reference with a painted 3MF."
            )
        bin_length,bin_type=struct.unpack("<II",handle.read(8))
        if bin_type!=0x004E4942:
            raise RuntimeError("GLB import contains no binary geometry buffer")
        binary=handle.read(bin_length)
    return document,binary

def matrix_multiply(left, right):
    return [sum(left[row*4+k]*right[k*4+column] for k in range(4))
            for row in range(4) for column in range(4)]

def glb_node_matrix(node):
    if "matrix" in node:
        raw=node["matrix"]
        return [float(raw[column*4+row]) for row in range(4) for column in range(4)]
    tx,ty,tz=(node.get("translation") or [0,0,0])
    sx,sy,sz=(node.get("scale") or [1,1,1])
    x,y,z,w=(node.get("rotation") or [0,0,0,1])
    rotation=[
        1-2*y*y-2*z*z, 2*x*y-2*z*w, 2*x*z+2*y*w, 0,
        2*x*y+2*z*w, 1-2*x*x-2*z*z, 2*y*z-2*x*w, 0,
        2*x*z-2*y*w, 2*y*z+2*x*w, 1-2*x*x-2*y*y, 0,
        0,0,0,1,
    ]
    scale=[sx,0,0,0, 0,sy,0,0, 0,0,sz,0, 0,0,0,1]
    translation=[1,0,0,tx, 0,1,0,ty, 0,0,1,tz, 0,0,0,1]
    return matrix_multiply(translation,matrix_multiply(rotation,scale))

def read_glb_accessor(document, binary, accessor_index):
    accessor=document["accessors"][accessor_index]
    view=document["bufferViews"][accessor["bufferView"]]
    if view.get("buffer",0)!=0 or "sparse" in accessor:
        raise RuntimeError("GLB sparse or external buffers are not supported for painted import")
    types={"SCALAR":1,"VEC2":2,"VEC3":3}
    formats={5121:"B",5123:"H",5125:"I",5126:"f"}
    components=types.get(accessor.get("type"))
    fmt=formats.get(accessor.get("componentType"))
    if components is None or fmt is None:
        raise RuntimeError("GLB accessor format is not supported for painted import")
    item_size=struct.calcsize("<"+fmt*components)
    stride=int(view.get("byteStride",item_size))
    start=int(view.get("byteOffset",0))+int(accessor.get("byteOffset",0))
    count=int(accessor.get("count",0))
    output=[]
    for index in range(count):
        offset=start+index*stride
        if offset+item_size>len(binary):
            raise RuntimeError("GLB accessor extends outside the binary buffer")
        output.append(struct.unpack_from("<"+fmt*components,binary,offset))
    return output

def import_glb_project(source, destination, temp_directory, internal_colors=48, progress=None):
    document,binary=read_glb_document(source)
    if len(document.get("images",[]))!=1:
        raise RuntimeError("GLB painted import currently supports exactly one embedded texture image")
    texture=glb_texture(source,temp_directory)
    if texture is None:
        raise RuntimeError("GLB painted import requires an embedded texture")
    positions=[]; coordinates=[]; faces=[]
    identity=[1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1]
    nodes=document.get("nodes",[])
    meshes=document.get("meshes",[])

    def transform(point, matrix):
        x,y,z=point
        return (
            matrix[0]*x+matrix[1]*y+matrix[2]*z+matrix[3],
            matrix[4]*x+matrix[5]*y+matrix[6]*z+matrix[7],
            matrix[8]*x+matrix[9]*y+matrix[10]*z+matrix[11],
        )
    def add_mesh(mesh_index, world):
        for primitive in meshes[mesh_index].get("primitives",[]):
            if primitive.get("mode",4)!=4 or "POSITION" not in primitive.get("attributes",{}) or "TEXCOORD_0" not in primitive.get("attributes",{}):
                raise RuntimeError("GLB painted import requires triangle primitives with POSITION and TEXCOORD_0")
            if "extensions" in primitive:
                raise RuntimeError("Compressed GLB primitives are not supported for painted import")
            points=read_glb_accessor(document,binary,primitive["attributes"]["POSITION"])
            texcoords=read_glb_accessor(document,binary,primitive["attributes"]["TEXCOORD_0"])
            if len(points)!=len(texcoords):
                raise RuntimeError("GLB position and UV accessor counts do not match")
            indices=(read_glb_accessor(document,binary,primitive["indices"]) if "indices" in primitive
                     else [(index,) for index in range(len(points))])
            flattened=[int(item[0]) for item in indices]
            if len(flattened)%3:
                raise RuntimeError("GLB triangle index accessor has incomplete faces")
            position_offset=len(positions); texture_offset=len(coordinates)
            positions.extend(transform(point,world) for point in points)
            coordinates.extend((float(point[0]),float(point[1])) for point in texcoords)
            for index in range(0,len(flattened),3):
                tri=flattened[index:index+3]
                if any(value<0 or value>=len(points) for value in tri):
                    raise RuntimeError("GLB face references a missing vertex")
                faces.append(tuple((position_offset+value,texture_offset+value) for value in tri))
                if len(faces)>MAX_IMPORT_FACES:
                    raise RuntimeError("GLB exceeds the 2,000,000-face import safety limit. Reduce the mesh first or use it as a visual reference with a painted 3MF.")
    def walk(node_index, parent):
        node=nodes[node_index]
        world=matrix_multiply(parent,glb_node_matrix(node))
        if "mesh" in node:
            add_mesh(int(node["mesh"]),world)
        for child in node.get("children",[]):
            walk(int(child),world)
    scene_index=int(document.get("scene",0))
    scene_nodes=(document.get("scenes") or [{}])[scene_index].get("nodes",[])
    if scene_nodes:
        for node in scene_nodes:
            walk(int(node),identity)
    else:
        for mesh_index in range(len(meshes)):
            add_mesh(mesh_index,identity)
    if not positions or not faces:
        raise RuntimeError("GLB import found no printable triangle mesh")
    scratch_obj=temp_directory/"glb_source.obj"
    scratch_mtl=temp_directory/"glb_source.mtl"
    scratch_mtl.write_text(f"newmtl texture\nmap_Kd {texture.name}\n")
    with scratch_obj.open("w") as handle:
        handle.write("mtllib glb_source.mtl\nusemtl texture\n")
        for x,y,z in positions:
            handle.write(f"v {x:.7f} {y:.7f} {z:.7f}\n")
        for u,v in coordinates:
            handle.write(f"vt {u:.7f} {v:.7f}\n")
        for triangle in faces:
            handle.write("f "+" ".join(f"{vertex+1}/{uv+1}" for vertex,uv in triangle)+"\n")
    result=import_obj_project(scratch_obj,destination,temp_directory,internal_colors=internal_colors,progress=progress)
    result["sourceType"]="Textured GLB"
    result["sourceFilename"]=source.name
    return result

def analyze_reference(reference, destination):
    if not reference:
        return None
    source=Path(reference).expanduser().resolve()
    if not source.is_file():
        raise RuntimeError("Reference file was not found")
    suffix=source.suffix.lower()
    if suffix==".glb":
        texture=glb_texture(source,destination)
        kind="GLB embedded texture"
    elif suffix==".obj":
        texture=obj_texture(source)
        kind="OBJ texture" if texture else "OBJ geometry only"
    elif suffix in (".png",".jpg",".jpeg",".bmp",".tif",".tiff"):
        texture=source
        kind="Texture image"
    else:
        raise RuntimeError("Reference mode accepts OBJ, GLB or a texture image")
    dominant=sample_reference_colors(texture,destination)
    return {
        "filename":source.name,
        "kind":kind,
        "hasTexture":texture is not None,
        "dominantColors":dominant,
    }

def project_mesh_metrics(archive):
    vertices=triangles=objects=texture_bytes=0
    for info in archive.infolist():
        lower=info.filename.lower()
        if lower.startswith("3d/objects/") and lower.endswith(".model"):
            objects+=1
            with archive.open(info) as source:
                for line in source:
                    vertices+=line.count(b"<vertex ")
                    triangles+=line.count(b"<triangle ")
        if "texture" in lower and not lower.endswith(".config"):
            texture_bytes+=info.file_size
    mode="Fast" if triangles>1000000 else ("Balanced" if triangles>250000 else "High")
    preview_memory=texture_bytes+vertices*32+triangles*12
    preview_seconds=max(0.1, round(triangles/220000, 1))
    return {
        "objectCount":objects,
        "vertexCount":vertices,
        "triangleCount":triangles,
        "polygonCount":triangles,
        "textureBytes":texture_bytes,
        "recommendedRenderMode":mode,
        "previewMemoryEstimateBytes":preview_memory,
        "previewBuildEstimateSeconds":preview_seconds,
    }

def inspect_project(infile, thumbnail_dest=None, preview_mesh_dest=None, mix_model="bambu", texture_override=None,
                    progress=lambda fraction,message: None, metadata_only=False):
    infile=Path(infile).expanduser().resolve()
    if infile.suffix.lower() in (".obj",".glb"):
        temporary=Path(tempfile.mkdtemp(prefix="fsinspectimport_"))
        try:
            staged=temporary/f"{infile.stem}_painted_source.3mf"
            progress(0.04, f"Opening textured {infile.suffix[1:].upper()} source")
            imported=(import_obj_project(infile,staged,temporary,texture_override,progress=progress)
                      if infile.suffix.lower()==".obj"
                      else import_glb_project(infile,staged,temporary,progress=progress))
            progress(0.60, "Generating source preview")
            result=inspect_project(staged,thumbnail_dest,preview_mesh_dest,mix_model)
            result.update({"input":str(infile),"filename":infile.name,"import":imported})
            return result
        finally:
            shutil.rmtree(temporary,ignore_errors=True)
    if infile.suffix.lower()!=".3mf":
        raise RuntimeError("Preview supports a painted 3MF or textured OBJ/GLB source")
    with zipfile.ZipFile(infile) as archive:
        validated_archive_infos(archive)
        psrel=find_project_settings(archive.namelist())
        if not psrel:
            raise RuntimeError("No project_settings.config found")
        obj,_=json.JSONDecoder().raw_decode(archive.read(psrel).decode("utf-8", errors="replace").lstrip())
        colors=colors_from_project(obj)
        if not colors:
            raise RuntimeError("No filament_colour array found")
        preview=None
        candidates=[
            "Metadata/plate_1.png",
            "Metadata/plate_no_light_1.png",
            "Metadata/top_1.png",
            "Metadata/pick_1.png",
        ]
        preview_name=next((name for name in candidates if name in archive.namelist()),None)
        if thumbnail_dest and preview_name:
            preview=Path(thumbnail_dest).expanduser()
            preview.parent.mkdir(parents=True,exist_ok=True)
            preview.write_bytes(archive.read(preview_name))
        metrics=None if metadata_only else project_mesh_metrics(archive)
        preview_mesh=None
        preview_notice=None
        if preview_mesh_dest and metrics and metrics["triangleCount"] > MAX_INTERACTIVE_PREVIEW_TRIANGLES:
            metrics["previewBuildEstimateSeconds"]=round(max(0.1,metrics["triangleCount"]/160000),1)
            progress(0.72,"Building optimized preview for large model")
            preview_mesh=export_preview_mesh(
                archive,preview_colors_from_project(obj,mix_model),preview_mesh_dest,
                grid_resolution=OPTIMIZED_PREVIEW_GRID_RESOLUTION,
            )
            preview_notice=(
                "Using optimized preview for large models. "
                "The full surface was reduced to an efficient display mesh."
            )
        elif preview_mesh_dest and not metadata_only:
            preview_mesh=export_preview_mesh(archive, preview_colors_from_project(obj,mix_model), preview_mesh_dest)
    return {
        "input":str(infile),
        "filename":infile.name,
        "sourceSlots":len(colors),
        "sourceColors":colors,
        "thumbnail":str(preview) if preview else None,
        "previewMesh":str(preview_mesh) if preview_mesh else None,
        "previewNotice":preview_notice,
        "metrics":metrics,
    }

def collect_paint_codes(tmp):
    ordered=[]
    seen=set()
    counts=Counter()
    for p in sorted((tmp/"3D"/"Objects").rglob("*.model")):
        if not p.is_file(): continue
        try: source=p.open("r", errors="replace")
        except Exception: continue
        with source:
            for text in source:
                for m in PAINT_PATTERN.finditer(text):
                    code=m.group(1).upper()
                    counts[code]+=1
                    if code not in seen:
                        ordered.append(code)
                        seen.add(code)
    return ordered, counts

def collect_archive_paint_codes(archive):
    ordered=[]
    seen=set()
    counts=Counter()
    model_names=sorted(n for n in archive.namelist()
                       if n.lower().startswith("3d/objects/") and n.lower().endswith(".model"))
    for name in model_names:
        with archive.open(name) as source:
            for raw_line in source:
                text=raw_line.decode("utf-8", errors="replace")
                for m in PAINT_PATTERN.finditer(text):
                    code=m.group(1).upper()
                    counts[code]+=1
                    if code not in seen:
                        ordered.append(code)
                        seen.add(code)
    return ordered, counts

def encode_paint_state(slot):
    if slot < 0 or slot > MAX_BAMBU_PAINT_SLOT:
        raise RuntimeError(f"Paint slot {slot} is outside BambuStudio's supported range 0-{MAX_BAMBU_PAINT_SLOT}")
    if slot < 3:
        return [slot << 2]
    n=slot-3
    out=[0xC]
    while n >= 15:
        out.append(0xF)
        n-=15
    out.append(n)
    return out

def remap_paint_code(code, slot_map=None, max_input_slot=None, max_output_slot=None):
    """
    Decode BambuStudio TriangleSelector facet serialization, replace leaf
    extruder states, and encode it again. Split-tree marker nibbles are kept.
    """
    code=str(code).strip().upper()
    if not code or any(ch not in HEX_DIGITS for ch in code):
        raise RuntimeError(f"Invalid Bambu paint_color code {code!r}")
    nibbles=[int(ch,16) for ch in reversed(code)]
    pos=0
    referenced=[]

    def take():
        nonlocal pos
        if pos >= len(nibbles):
            raise RuntimeError(f"Truncated Bambu paint_color code {code!r}")
        value=nibbles[pos]
        pos+=1
        return value

    def visit():
        marker=take()
        split_sides=marker & 0x3
        if split_sides:
            output=[marker]
            for _ in range(split_sides+1):
                output.extend(visit())
            return output

        if marker & 0xC == 0xC:
            state=3
            ext=take()
            while ext == 0xF:
                state+=15
                ext=take()
            state+=ext
        else:
            state=marker >> 2

        if state:
            if max_input_slot is not None and state > max_input_slot:
                raise RuntimeError(f"paint_color {code!r} references missing slot {state} (only {max_input_slot} exist)")
            referenced.append(state)
        mapped=slot_map.get(state, state) if slot_map and state else state
        if mapped and max_output_slot is not None and mapped > max_output_slot:
            raise RuntimeError(f"Mapped paint_color {code!r} references missing output slot {mapped} (only {max_output_slot} exist)")
        return encode_paint_state(mapped)

    output=visit()
    if pos != len(nibbles):
        raise RuntimeError(f"Extra serialized data in Bambu paint_color code {code!r}")
    mapped_code="".join(HEX_DIGITS[n] for n in reversed(output))
    return mapped_code, referenced

def paint_slot_usage(code_counts, slot_count):
    usage=Counter()
    for code,count in code_counts.items():
        _, referenced=remap_paint_code(code, max_input_slot=slot_count, max_output_slot=slot_count)
        for slot in referenced:
            usage[slot]+=count
    return usage

def preview_face_slot(code, slot_count):
    if not code:
        return 1
    _,referenced=remap_paint_code(code, max_input_slot=slot_count, max_output_slot=slot_count)
    return Counter(referenced).most_common(1)[0][0] if referenced else 1

def write_preview_materials(path, colors, material_prefix):
    with path.open("w") as output:
        for slot,color in enumerate(colors,start=1):
            red,green,blue=(channel/255.0 for channel in rgb(color))
            output.write(f"newmtl {material_prefix}_{slot}\nKd {red:.4f} {green:.4f} {blue:.4f}\nKa {red*.16:.4f} {green*.16:.4f} {blue*.16:.4f}\nNs 22\n\n")

def export_preview_mesh(archive, colors, destination, material_prefix="slot",
                        grid_resolution=PREVIEW_GRID_RESOLUTION):
    """
    Write a reduced, colored viewport mesh without altering print geometry.
    Object XML can be hundreds of megabytes, so this reads line-oriented 3MF
    vertex/triangle records and clusters nearby display vertices.
    """
    destination=Path(destination).expanduser()
    destination.parent.mkdir(parents=True,exist_ok=True)
    obj_path=destination.with_suffix(".obj")
    mtl_path=obj_path.with_suffix(".mtl")
    model_names=sorted(
        name for name in archive.namelist()
        if name.lower().startswith("3d/objects/") and name.lower().endswith(".model")
    )
    if not model_names:
        return None

    source_vertices=array("f")
    offsets={}
    low=[float("inf")]*3
    high=[float("-inf")]*3
    for name in model_names:
        offsets[name]=len(source_vertices)//3
        with archive.open(name) as source:
            for raw_line in source:
                if b"<vertex " not in raw_line:
                    continue
                text=raw_line.decode("utf-8", errors="replace")
                for tag in VERTEX_TAG_PATTERN.findall(text):
                    attrs=dict(XML_ATTRIBUTE_PATTERN.findall(tag))
                    try:
                        values=[float(attrs[key]) for key in ("x","y","z")]
                    except (KeyError,ValueError):
                        continue
                    source_vertices.extend(values)
                    for axis,value in enumerate(values):
                        low[axis]=min(low[axis],value)
                        high[axis]=max(high[axis],value)
    if not source_vertices:
        return None

    max_extent=max(high[axis]-low[axis] for axis in range(3)) or 1.0
    cell=max_extent/max(8,int(grid_resolution))
    clustered={}
    display_vertices=[]
    display_faces={}

    def display_index(source_index):
        base=source_index*3
        if base+2 >= len(source_vertices):
            return None
        point=(source_vertices[base],source_vertices[base+1],source_vertices[base+2])
        key=tuple(int(math.floor((point[axis]-low[axis])/cell)) for axis in range(3))
        mapped=clustered.get(key)
        if mapped is None:
            mapped=len(display_vertices)+1
            clustered[key]=mapped
            display_vertices.append(point)
        return mapped

    for name in model_names:
        offset=offsets[name]
        with archive.open(name) as source:
            for raw_line in source:
                if b"<triangle " not in raw_line:
                    continue
                text=raw_line.decode("utf-8", errors="replace")
                for tag in TRIANGLE_TAG_PATTERN.findall(text):
                    attrs=dict(XML_ATTRIBUTE_PATTERN.findall(tag))
                    try:
                        mapped=tuple(display_index(offset+int(attrs[key])) for key in ("v1","v2","v3"))
                    except (KeyError,ValueError):
                        continue
                    if None in mapped or len(set(mapped)) < 3:
                        continue
                    face_key=tuple(sorted(mapped))
                    if face_key not in display_faces:
                        display_faces[face_key]=(mapped,preview_face_slot(attrs.get("paint_color"),len(colors)))

    faces_by_slot={}
    for mapped,slot in display_faces.values():
        faces_by_slot.setdefault(slot,[]).append(mapped)
    write_preview_materials(mtl_path,colors,material_prefix)
    with obj_path.open("w") as output:
        output.write(f"mtllib {mtl_path.name}\n")
        output.write("# Reduced viewport mesh generated from painted 3MF facets.\n")
        for x,y,z in display_vertices:
            output.write(f"v {x:.5f} {y:.5f} {z:.5f}\n")
        output.write("s 1\n")
        for slot in sorted(faces_by_slot):
            output.write(f"usemtl {material_prefix}_{slot}\n")
            for first,second,third in faces_by_slot[slot]:
                output.write(f"f {first} {second} {third}\n")
    return obj_path

def preview_slot_usage(archive, slot_count, grid_resolution=OPTIMIZED_PREVIEW_GRID_RESOLUTION):
    """
    Count painted slots after the same grid-reduction used by the viewport OBJ.
    This is a planning sample, not the final remap source: hidden/small paint
    states still get a guard weight from the original paint-state usage.
    """
    model_names=sorted(
        name for name in archive.namelist()
        if name.lower().startswith("3d/objects/") and name.lower().endswith(".model")
    )
    if not model_names:
        return Counter()

    source_vertices=array("f")
    offsets={}
    low=[float("inf")]*3
    high=[float("-inf")]*3
    for name in model_names:
        offsets[name]=len(source_vertices)//3
        with archive.open(name) as source:
            for raw_line in source:
                if b"<vertex " not in raw_line:
                    continue
                text=raw_line.decode("utf-8", errors="replace")
                for tag in VERTEX_TAG_PATTERN.findall(text):
                    attrs=dict(XML_ATTRIBUTE_PATTERN.findall(tag))
                    try:
                        values=[float(attrs[key]) for key in ("x","y","z")]
                    except (KeyError,ValueError):
                        continue
                    source_vertices.extend(values)
                    for axis,value in enumerate(values):
                        low[axis]=min(low[axis],value)
                        high[axis]=max(high[axis],value)
    if not source_vertices:
        return Counter()

    max_extent=max(high[axis]-low[axis] for axis in range(3)) or 1.0
    cell=max_extent/max(8,int(grid_resolution))
    clustered={}
    display_faces={}

    def display_index(source_index):
        base=source_index*3
        if base+2 >= len(source_vertices):
            return None
        point=(source_vertices[base],source_vertices[base+1],source_vertices[base+2])
        key=tuple(int(math.floor((point[axis]-low[axis])/cell)) for axis in range(3))
        mapped=clustered.get(key)
        if mapped is None:
            mapped=len(clustered)+1
            clustered[key]=mapped
        return mapped

    for name in model_names:
        offset=offsets[name]
        with archive.open(name) as source:
            for raw_line in source:
                if b"<triangle " not in raw_line:
                    continue
                text=raw_line.decode("utf-8", errors="replace")
                for tag in TRIANGLE_TAG_PATTERN.findall(text):
                    attrs=dict(XML_ATTRIBUTE_PATTERN.findall(tag))
                    try:
                        mapped=tuple(display_index(offset+int(attrs[key])) for key in ("v1","v2","v3"))
                    except (KeyError,ValueError):
                        continue
                    if None in mapped or len(set(mapped)) < 3:
                        continue
                    face_key=tuple(sorted(mapped))
                    if face_key not in display_faces:
                        display_faces[face_key]=preview_face_slot(attrs.get("paint_color"),slot_count)
    return Counter(display_faces.values())

def blend_preview_usage(paint_usage, preview_usage):
    paint_total=sum(paint_usage.values()) or 1.0
    preview_total=sum(preview_usage.values()) or 1.0
    blended=Counter()
    slots=set(paint_usage) | set(preview_usage)
    for slot in slots:
        paint_weight=float(paint_usage.get(slot,0.0))
        preview_weight=float(preview_usage.get(slot,0.0)) * (paint_total/preview_total)
        blended[slot]=preview_weight*PREVIEW_USAGE_BLEND + paint_weight*(1.0-PREVIEW_USAGE_BLEND)
    return blended

def recolor_preview_mesh(source_mesh, colors, destination, material_prefix):
    """Reuse reduced preview geometry for another analytical color overlay."""
    source_mesh=Path(source_mesh)
    destination=Path(destination).expanduser().with_suffix(".obj")
    destination.parent.mkdir(parents=True,exist_ok=True)
    write_preview_materials(destination.with_suffix(".mtl"),colors,material_prefix)
    with source_mesh.open("r") as source, destination.open("w") as output:
        first=source.readline()
        output.write(f"mtllib {destination.with_suffix('.mtl').name}\n")
        if not first.startswith("mtllib "):
            output.write(first)
        shutil.copyfileobj(source,output)
    return destination

def anchor_name(anchor):
    return anchor["name"]

def anchor_color(anchor):
    return anchor["color"]

def anchor_key(anchor):
    return f"{str(anchor.get('series') or filament_family(anchor_name(anchor))).strip()}|{anchor_color(anchor)}"

def anchor_option_payload(anchor):
    series=str(anchor.get("series") or filament_family(anchor_name(anchor))).strip()
    preset,filament_id=profile_for_anchor(series)
    return {
        "key":anchor_key(anchor),
        "name":anchor_name(anchor),
        "series":series,
        "brand":str(anchor.get("brand") or "Bambu Lab"),
        "color":anchor_color(anchor),
        "preset":str(anchor.get("preset") or preset),
        "filamentID":str(anchor.get("filamentID") or filament_id),
        "remainingGrams":anchor.get("remainingGrams"),
        "availability":anchor.get("availability"),
        "catalogSource":anchor.get("catalogSource"),
    }

def parse_csv_tokens(value):
    if value is None:
        return []
    if isinstance(value,(list,tuple,set)):
        raw=[]
        for item in value:
            raw.extend(parse_csv_tokens(item))
        return raw
    return [part.strip() for part in re.split(r"[,;]", str(value)) if part.strip()]

def normalize_material_families(value):
    requested=parse_csv_tokens(value)
    if not requested:
        return []
    valid={family.lower():family for family in PROFILE_BY_FAMILY if supported_catalog_family(family,"all")}
    aliases={
        "all":"all",
        "auto":"all",
        "*":"all",
        "default":"all",
    }
    normalized=[]
    for item in requested:
        lookup=aliases.get(item.lower(), item.lower())
        if lookup=="all":
            return []
        family=valid.get(lookup)
        if family is None:
            raise RuntimeError(
                f"Unknown or unsupported Bambu material family {item!r}. "
                "Choose Bambu PLA families such as PLA Basic, PLA Matte, PLA Silk+, or PLA Pure."
            )
        if family not in normalized:
            normalized.append(family)
    return normalized

def normalize_anchor_keys(value):
    return parse_csv_tokens(value)

def filter_material_families(pool, material_families=None):
    families=set(normalize_material_families(material_families))
    if not families:
        return list(pool)
    return [item for item in pool if str(item.get("series") or filament_family(anchor_name(item))).strip() in families]

def anchor_matches_key(anchor, key):
    normalized=str(key or "").strip()
    if not normalized:
        return False
    lowered=normalized.lower()
    return (
        anchor_key(anchor).lower()==lowered
        or anchor_color(anchor).lower()==lowered
        or anchor_name(anchor).lower()==lowered
    )

def resolve_pinned_anchors(pool, anchor_keys):
    resolved=[]
    missing=[]
    for key in normalize_anchor_keys(anchor_keys):
        match=next((candidate for candidate in pool if anchor_matches_key(candidate,key)),None)
        if match is None:
            missing.append(key)
            continue
        if anchor_color(match) not in {anchor_color(anchor) for anchor in resolved}:
            resolved.append(match)
    if missing:
        raise RuntimeError(
            "Selected anchor filaments are not available with the current filament source/material filters: "
            + ", ".join(missing)
        )
    return resolved

def nearest_anchor_error(color, anchors):
    return min((dist(color,anchor_color(anchor)),i+1,anchor_name(anchor),anchor_color(anchor))
               for i,anchor in enumerate(anchors))

def best_mix_recipe(color, anchors, mix_model="bambu", allow_three=True, high_fidelity=False):
    best_err=999999.0; best=None
    pair_family="fine2" if high_fidelity else "standard2"
    for component_slots,ratios,preview in mix_recipe_index(anchors,mix_model,pair_family,"none"):
        d=dist(color,preview)
        if d<best_err:
            best_err=d; best=(list(component_slots),list(ratios),preview)
    if best is None:
        direct=nearest_anchor_error(color,anchors)
        return [direct[1]],[1.0],direct[3],direct[0]
    three_color_trigger=0.0 if high_fidelity else 12.0
    if allow_three and best_err>three_color_trigger:
        best3_err=best_err; best3=best
        triple_family="fine3" if high_fidelity else "standard3"
        for component_slots,ratios,preview in mix_recipe_index(anchors,mix_model,"none",triple_family):
            d=dist(color,preview)
            if d<best3_err:
                best3_err=d; best3=(list(component_slots),list(ratios),preview)
        required_gain=0.35 if high_fidelity else 2.5
        required_ratio=0.02 if high_fidelity else 0.15
        if (best_err-best3_err)>=required_gain and ((best_err-best3_err)/max(best_err,1e-9))>=required_ratio:
            best_err=best3_err; best=best3
    return best[0],best[1],best[2],best_err

def select_cmykw_anchors(pool, count):
    remaining=pool[:]
    selected=[]
    for role,target in CMYK_TARGETS[:count]:
        match=min(remaining,key=lambda spool:dist(target,spool["color"]))
        anchor=dict(match)
        anchor["role"]=role
        anchor["name"]=f"{role} / {match['name']}"
        selected.append(anchor)
        remaining=[candidate for candidate in remaining if candidate["color"] != match["color"]]
    return selected

def weighted_color_targets(old_colors, usage, reference=None, quality_bias=DEFAULT_QUALITY_BIAS):
    usage=usage or {}
    used=[(i+1,c,float(usage.get(i+1,0))) for i,c in enumerate(old_colors) if usage.get(i+1,0)>0]
    if not used:
        used=[(i+1,c,1.0) for i,c in enumerate(old_colors)]
    total=sum(w for _,_,w in used) or 1.0
    targets=list(used)
    if reference and reference.get("dominantColors"):
        # A source texture can expose important colors which sparse painted
        # facet usage understates. Keep it influential, never dominant.
        reference_weight=total*(0.10+0.001*clamp_quality_bias(quality_bias))
        targets.extend((0,item["color"],reference_weight*item["weight"])
                       for item in reference["dominantColors"])
    target_total=sum(w for _,_,w in targets) or 1.0
    return used,total,targets,target_total

def unique_palette_options(pool):
    unique=[]
    seen=set()
    for item in pool:
        color=anchor_color(item)
        if color in seen:
            continue
        seen.add(color)
        unique.append(item)
    return unique

def color_saturation(color):
    channels=rgb(color)
    return max(channels)-min(channels)

def color_hue_degrees(color):
    r,g,b=(channel/255.0 for channel in rgb(color))
    hue,saturation,_=colorsys.rgb_to_hsv(r,g,b)
    if saturation < 0.08:
        return None
    return hue*360.0

def spectrum_bucket(color):
    hue=color_hue_degrees(color)
    if hue is None:
        lum=luminance(color)
        if lum < 70:
            return "neutral-dark"
        if lum > 205:
            return "neutral-light"
        return "neutral-mid"
    return f"hue-{int(hue//45)%8}"

def spectrum_distance(target, candidate):
    base=dist(target,anchor_color(candidate))
    target_bucket=spectrum_bucket(target)
    candidate_bucket=spectrum_bucket(anchor_color(candidate))
    if target_bucket==candidate_bucket:
        return base*0.82
    if target_bucket.startswith("neutral") or candidate_bucket.startswith("neutral"):
        return base+2.2
    return base+4.0

def anchor_signature(anchors):
    return tuple(anchor_color(anchor) for anchor in anchors)

def distinct_anchor_set(anchors):
    colors=[anchor_color(anchor) for anchor in anchors]
    if len(colors) != len(set(colors)):
        return False
    return not any(dist(anchor_color(a),anchor_color(b))<MIN_ANCHOR_DE
                   for ix,a in enumerate(anchors) for b in anchors[ix+1:])

def shortlist_anchor_pool(pool, targets, target_total, limit=ANCHOR_POOL_LIMIT):
    pool=unique_palette_options(pool)
    if len(pool) <= limit:
        return pool
    selected=[]
    selected_colors=set()
    def add(candidate):
        color=anchor_color(candidate)
        if color not in selected_colors:
            selected.append(candidate)
            selected_colors.add(color)
    significant=sorted(targets,key=lambda item:item[2],reverse=True)[:14]
    for _,color,_ in significant:
        for candidate in sorted(pool,key=lambda item:dist(color,anchor_color(item)))[:4]:
            add(candidate)
    by_spectrum=defaultdict(list)
    for _,color,weight in targets:
        by_spectrum[spectrum_bucket(color)].append((color,weight))
    for _,bucket_items in sorted(
        by_spectrum.items(),
        key=lambda item:sum(weight for _,weight in item[1]),
        reverse=True,
    )[:10]:
        representative=max(bucket_items,key=lambda item:item[1])[0]
        for candidate in sorted(pool,key=lambda item:spectrum_distance(representative,item))[:5]:
            add(candidate)
    for sorter in (
        lambda item:luminance(anchor_color(item)),
        lambda item:-luminance(anchor_color(item)),
        lambda item:-color_saturation(anchor_color(item)),
    ):
        for candidate in sorted(pool,key=sorter)[:8]:
            add(candidate)
    coverage=sorted(
        pool,
        key=lambda item:sum((weight/target_total)*dist(color,anchor_color(item))
                            for _,color,weight in targets),
    )
    for candidate in coverage:
        add(candidate)
        if len(selected) >= limit:
            break
    return selected

def palette_usage_stats(rows, usage, quality_bias):
    usage=usage or {}
    weights={slot:float(usage.get(slot,0)) for slot,*_ in rows}
    total=sum(weights.values()) or 1.0
    mixed_rows=[row for row in rows if row[3]=="MIX"]
    mixed_slots=len({row[1] for row in mixed_rows})
    mixed_share=sum(weights.get(row[0],0.0) for row in mixed_rows)/total
    limit=quality_mix_limit(quality_bias)
    weak_share=sum(weights.get(row[0],0.0) for row in rows if float(row[8])>limit)/total
    return mixed_slots,mixed_share,weak_share

def palette_selection_score(old_colors, usage, anchors, quality_bias, mix_model="bambu", reference=None,
                            planner_mode="best"):
    newc,_,_,_,_,rows=build_palette(old_colors,anchors,usage,quality_bias,mix_model,planner_mode)
    metrics=quality_metrics(rows,usage,old_colors,reference,mix_model)
    mixed_slots,mixed_share,weak_share=palette_usage_stats(rows,usage,quality_bias)
    practical_pressure=(100-clamp_quality_bias(quality_bias))/100
    score=(
        metrics["estimatedDeltaE"]
        + metrics["maximumDeltaE"]*PALETTE_MAX_ERROR_WEIGHT
        + mixed_slots*(0.05+0.12*practical_pressure)
        + mixed_share*(0.45+0.55*practical_pressure)
        + weak_share*3.0
        - metrics.get("contrastRetention",0)*0.003
    )
    return score,newc,rows,metrics,mixed_slots,mixed_share

def select_anchors(old_colors, usage, mode, inventory, palette_source, real_slots="auto",
                   custom_catalog_path=None, reference=None, mix_model="bambu",
                   quality_bias=DEFAULT_QUALITY_BIAS, planner_mode="best",
                   material_families=None, pinned_anchor_keys=None):
    planner_mode=normalize_planner_mode(planner_mode)
    material_families=normalize_material_families(material_families)
    pinned_anchor_keys=normalize_anchor_keys(pinned_anchor_keys)
    requested=None if str(real_slots)=="auto" else int(real_slots)
    mix_limit=quality_mix_limit(quality_bias)
    minimum=4 if mode=="cmykw" else MIN_REAL_SLOTS
    maximum=maximum_requested_slots_for_mode(mode)
    if requested is not None and (requested<minimum or requested>maximum):
        raise RuntimeError(f"{mode.upper()} strategy requires {minimum}-{maximum} physical slots")
    if palette_source=="exact-cmykw":
        if material_families:
            raise RuntimeError("Material-family filters are not used with Exact CMYKW.")
        if pinned_anchor_keys:
            raise RuntimeError("Manual anchor pins are not used with Exact CMYKW.")
        if mode!="cmykw":
            raise RuntimeError("Exact CMYKW filament source requires the CMYKW palette strategy")
        return exact_cmykw_palette()[:requested or maximum]
    if mode=="cmykw" and pinned_anchor_keys:
        raise RuntimeError("Manual anchor pins are available for Bambu PLA strategy. CMYKW chooses cyan, magenta, yellow, black and white roles.")
    if palette_source=="inventory":
        pool=inventory_palette(inventory)
    elif palette_source=="custom":
        if material_families:
            raise RuntimeError("Material-family filters are available for Bambu filament sources, not custom JSON libraries.")
        if pinned_anchor_keys:
            raise RuntimeError("Manual anchor pins are available for Bambu filament sources, not custom JSON libraries.")
        pool=custom_palette(custom_catalog_path)
    else:
        pool=catalog_palette("all" if palette_source=="all-bambu" else "core",inventory,material_families)
    if palette_source=="inventory":
        pool=filter_material_families(pool,material_families)
    pinned_anchors=resolve_pinned_anchors(pool,pinned_anchor_keys)
    if requested is not None and len(pinned_anchors)>requested:
        raise RuntimeError(f"{len(pinned_anchors)} manual anchors were selected, but Physical slots is {requested}.")
    used,total,targets,target_total=weighted_color_targets(old_colors,usage,reference,quality_bias)
    if mode!="cmykw":
        pool=shortlist_anchor_pool(pool,targets,target_total,anchor_pool_limit_for_quality(quality_bias,planner_mode))
        for anchor in reversed(pinned_anchors):
            if anchor_color(anchor) not in {anchor_color(candidate) for candidate in pool}:
                pool.insert(0,anchor)
    else:
        pool=unique_palette_options(pool)
    score_hints=()
    if mode!="cmykw":
        score_hints=anchor_score_hint_database(
            tuple(anchor_color(anchor) for anchor in pool),
            tuple(color for _,color,_ in targets),
            mix_model,
            score_pair_family(quality_bias,planner_mode),
            score_triple_family(quality_bias,planner_mode),
            round(mix_limit,3),
        )
    score_cache={}
    full_palette_score_cache={}
    def score(anchors):
        if not anchors:
            return 999999.0
        score_key=tuple(sorted(anchor_signature(anchors)))
        cached=score_cache.get(score_key)
        if cached is not None:
            return cached
        ah=[anchor_color(anchor) for anchor in anchors]
        anchor_colors=set(ah)
        s=0.0
        for target_index,(_,c,w) in enumerate(targets):
            direct=min(dist(c,a) for a in ah)
            candidate=direct
            if target_index < len(score_hints):
                for components,error in score_hints[target_index]:
                    if error>=candidate:
                        break
                    if all(component in anchor_colors for component in components):
                        candidate=error
                        break
            s+=(w/target_total)*candidate
        lums=[luminance(a) for a in ah]
        if max(lums)<210: s+=12
        if min(lums)>65: s+=12
        for i in range(len(ah)):
            for j in range(i+1,len(ah)):
                d=dist(ah[i],ah[j])
                if d<MIN_ANCHOR_DE: s+=(MIN_ANCHOR_DE-d)*4
        score_cache[score_key]=s
        return s
    def greedy_fill(start, count):
        selected=list(start)
        while len(selected)<count:
            best=None
            for cand in pool:
                if cand in selected:
                    continue
                trial=selected+[cand]
                if not distinct_anchor_set(trial):
                    continue
                candidate=(score(trial),cand)
                if best is None or candidate[0]<best[0]:
                    best=candidate
            if best is None:
                best=next(((0,cand) for cand in pool if cand not in selected),None)
            if best is None:
                raise RuntimeError("Could not find enough distinct physical filament anchors")
            selected.append(best[1])
        return selected
    def full_palette_score(current):
        key=tuple(sorted(anchor_signature(current)))
        cached=full_palette_score_cache.get(key)
        if cached is not None:
            return cached
        value=palette_selection_score(old_colors,usage,current,quality_bias,mix_model,reference,planner_mode)[0]
        full_palette_score_cache[key]=value
        return value
    def local_optimize(current, fixed_count=0):
        current=list(current)
        best_score=full_palette_score(current)
        if planner_mode!="best":
            return current,best_score
        best_anchors=list(current)
        passes=2 if high_fidelity_quality(quality_bias,planner_mode) else 1
        for _ in range(passes):
            improved=False
            for index in range(len(best_anchors)):
                if index < fixed_count:
                    continue
                proxy_trials=[]
                for candidate in pool:
                    if any(anchor_color(candidate)==anchor_color(anchor) for slot,anchor in enumerate(best_anchors) if slot != index):
                        continue
                    trial=list(best_anchors)
                    trial[index]=candidate
                    if not distinct_anchor_set(trial):
                        continue
                    proxy_trials.append((score(trial),trial))
                for _,trial in sorted(proxy_trials,key=lambda item:item[0])[:LOCAL_OPTIMIZE_CANDIDATE_LIMIT]:
                    trial_score=full_palette_score(trial)
                    if trial_score < best_score - 0.02:
                        best_anchors=trial
                        best_score=trial_score
                        improved=True
            if not improved:
                break
        return best_anchors,best_score
    def beam_candidates(count):
        beams=[()]
        for _ in range(count):
            expanded=[]
            for beam in beams:
                current=list(beam)
                for candidate in pool:
                    if candidate in current:
                        continue
                    trial=current+[candidate]
                    if not distinct_anchor_set(trial):
                        continue
                    expanded.append((score(trial),tuple(trial)))
            kept=[]
            seen=set()
            for _,trial in sorted(expanded,key=lambda item:item[0]):
                key=tuple(sorted(anchor_signature(trial)))
                if key in seen:
                    continue
                seen.add(key)
                kept.append(trial)
                if len(kept)>=anchor_beam_width_for_quality(quality_bias,planner_mode):
                    break
            beams=kept
            if not beams:
                break
        return [list(beam) for beam in beams if len(beam)==count]
    def choose_count(count):
        if len(pinned_anchors)>count:
            raise RuntimeError(f"{len(pinned_anchors)} manual anchors were selected, but this plan only allows {count} physical slots.")
        if len({anchor_color(item) for item in pool})<count:
            raise RuntimeError(f"Filament source contains fewer than {count} distinct colors")
        if mode=="cmykw":
            return select_cmykw_anchors(pool,count)
        base_start=list(pinned_anchors)
        starts=[base_start]
        seeded=[]
        if any(luminance(c)>205 and (w/total)>.01 for _,c,w in used):
            seeded.append(min(pool,key=lambda b:abs(luminance(anchor_color(b))-245)))
        if len(seeded)<count and any(luminance(c)<75 and (w/total)>.01 for _,c,w in used):
            dark=min(pool,key=lambda b:luminance(anchor_color(b)))
            if dark not in seeded:
                seeded.append(dark)
        if seeded and distinct_anchor_set(seeded):
            starts.append((base_start+seeded)[:count])
        for _,color,_ in sorted(used,key=lambda item:item[2],reverse=True)[:min(6,len(used))]:
            starts.append(base_start+[min(pool,key=lambda candidate:dist(color,anchor_color(candidate)))])
        if not pinned_anchors:
            starts.extend(beam_candidates(count))
        best=None
        seen=set()
        for start in starts:
            if len(start)>count or not distinct_anchor_set(start):
                continue
            try:
                filled=start if len(start)==count else greedy_fill(start,count)
                current,current_score=filled,full_palette_score(filled)
            except RuntimeError:
                continue
            key=tuple(sorted(anchor_signature(current)))
            if key in seen:
                continue
            seen.add(key)
            if best is None or current_score<best[0]:
                best=(current_score,current)
        if best is None:
            raise RuntimeError("Could not find enough distinct physical filament anchors")
        if planner_mode=="best":
            return local_optimize(best[1], fixed_count=len(pinned_anchors))[0]
        return best[1]
    counts=[requested] if requested is not None else [
        count for count in automatic_slot_counts_for_mode(mode)
        if count >= len(pinned_anchors)
    ]
    if requested is None and mode!="cmykw":
        active_target_colors=len({hx(color) for _,color,weight in used if weight>0})
        if active_target_colors>=18:
            counts=[count for count in counts if count>=5]
        elif active_target_colors>=10:
            counts=[count for count in counts if count>=4]
    if not counts:
        raise RuntimeError(f"{len(pinned_anchors)} manual anchors were selected, but the automatic slot range cannot fit them.")
    trials=[]
    for count in counts:
        anchors=choose_count(count)
        weighted=palette_selection_score(old_colors,usage,anchors,quality_bias,mix_model,reference,planner_mode)[0]
        # A new physical slot must buy noticeable visual improvement.
        physical_penalty=(count-minimum)*(1.35-(clamp_quality_bias(quality_bias)/100)*0.9)
        trials.append((weighted+physical_penalty,weighted,anchors))
    return min(trials,key=lambda trial:trial[0])[2]

def build_palette(old_colors, anchors, usage=None, quality_bias=DEFAULT_QUALITY_BIAS,
                  mix_model="bambu", planner_mode="best"):
    planner_mode=normalize_planner_mode(planner_mode)
    real_count=len(anchors)
    newc=[anchor_color(anchor) for anchor in anchors]
    ism=["0"]*real_count; comps=[""]*real_count; ratios=[""]*real_count
    old_slot_to_new_slot={}
    rows_by_slot={}
    next_slot=real_count+1
    quality_bias=clamp_quality_bias(quality_bias)
    mix_limit=quality_mix_limit(quality_bias)
    min_gain=MIN_MIX_GAIN+(100-quality_bias)*0.045
    high_fidelity=high_fidelity_quality(quality_bias,planner_mode)
    if high_fidelity:
        min_gain=max(0.3,min_gain*0.45)
    max_unique_mixes=max(2,min(MAX_BAMBU_PAINT_SLOT-real_count,3+round(quality_bias/6)))
    if high_fidelity:
        max_unique_mixes=max(max_unique_mixes,min(MAX_BAMBU_PAINT_SLOT-real_count,8+round(quality_bias/4)))
    mix_candidates=[]
    for old_slot,target in enumerate(old_colors, start=1):
        direct_err,direct_slot,direct_name,direct_hex=nearest_anchor_error(target,anchors)
        cs,rs,preview,mix_err=best_mix_recipe(
            target,
            anchors,
            mix_model,
            allow_three=quality_bias>=70,
            high_fidelity=high_fidelity,
        )
        gain=direct_err-mix_err
        weight=float((usage or {}).get(old_slot,1.0))
        old_slot_to_new_slot[old_slot]=direct_slot
        rows_by_slot[old_slot]=[old_slot,direct_slot,target,"ANCHOR",direct_name,"","",
                                direct_hex,f"{direct_err:.2f}",f"{direct_err:.2f}","0.00"]
        if weight>0 and direct_err>DIRECT_ANCHOR_DE and gain>=min_gain and mix_err<=mix_limit:
            mix_candidates.append((gain*weight,gain,old_slot,target,cs,rs,preview,mix_err,direct_err))
    recipes={}
    for _,gain,old_slot,target,cs,rs,preview,mix_err,direct_err in sorted(mix_candidates,reverse=True):
        key=(tuple(cs),tuple(round(x,4) for x in rs))
        if key not in recipes and len(recipes)>=max_unique_mixes:
            continue
        if key not in recipes:
            recipes[key]=next_slot
            newc.append(preview)
            ism.append("1")
            comps.append(",".join(map(str,cs)))
            ratios.append(",".join(f"{x:.4f}" for x in rs))
            next_slot+=1
        mapped_slot=recipes[key]
        old_slot_to_new_slot[old_slot]=mapped_slot
        rows_by_slot[old_slot]=[old_slot,mapped_slot,target,"MIX","",",".join(map(str,cs)),
                                ",".join(f"{x:.4f}" for x in rs),preview,f"{mix_err:.2f}",
                                f"{direct_err:.2f}",f"{gain:.2f}"]
    return newc,ism,comps,ratios,old_slot_to_new_slot,[rows_by_slot[i] for i in sorted(rows_by_slot)]

def source_slot_representatives(old_colors, anchors, old_slot_to_new_slot, rows, newn):
    real_count=len(anchors)
    representatives=[]
    for new_slot,anchor in enumerate(anchors,start=1):
        mapped=[old_slot for old_slot,mapped_slot in old_slot_to_new_slot.items() if mapped_slot==new_slot]
        candidates=mapped or list(range(1,len(old_colors)+1))
        representatives.append(min(candidates,key=lambda old_slot:dist(old_colors[old_slot-1],anchor_color(anchor))))
    mixed_source={new_slot:old_slot for old_slot,new_slot,*_ in rows if new_slot>real_count}
    for new_slot in range(real_count+1,newn+1):
        representatives.append(mixed_source[new_slot])
    return representatives

def heatmap_color(error):
    if error <= 2.0:
        return "#37C977"
    if error <= 6.0:
        ratio=(error-2.0)/4.0
        return tohex(55+190*ratio,201+14*ratio,119-82*ratio)
    ratio=min(1.0,(error-6.0)/12.0)
    return tohex(245,215-141*ratio,37-6*ratio)

def quality_metrics(rows, usage, old_colors=None, reference=None, mix_model="bambu"):
    fallback=0 if usage else 1
    weights={slot:float(usage.get(slot,fallback)) for slot,*_ in rows}
    total=sum(weights.values()) or 1.0
    errors=[(float(row[8]),weights[row[0]]) for row in rows if weights[row[0]]>0]
    estimated=sum(error*weight for error,weight in errors)/total
    maximum=max((error for error,_ in errors),default=0.0)
    mean_score=max(0.0,100.0-estimated*2.2)
    maximum_score=max(0.0,100.0-maximum*QUALITY_MAX_ERROR_WEIGHT)
    result={
        "estimatedDeltaE":round(estimated,2),
        "maximumDeltaE":round(maximum,2),
        "qualityScore":round(min(mean_score,maximum_score),1),
    }
    predictions={row[0]:row[7] for row in rows}
    if old_colors:
        weighted_brightness=0.0
        weighted_contrast=0.0
        original_contrast=0.0
        for slot,color in enumerate(old_colors,start=1):
            weight=weights.get(slot,0.0)/total
            if weight:
                weighted_brightness+=weight*abs(rgb_to_lab(*rgb(color))[0]-rgb_to_lab(*rgb(predictions[slot]))[0])
        for first in range(1,len(old_colors)+1):
            for second in range(first+1,len(old_colors)+1):
                pair_weight=(weights.get(first,0.0)*weights.get(second,0.0))/(total*total)
                if not pair_weight:
                    continue
                original=dist(old_colors[first-1],old_colors[second-1])
                predicted=dist(predictions[first],predictions[second])
                original_contrast+=pair_weight*original
                weighted_contrast+=pair_weight*abs(original-predicted)
        result["brightnessError"]=round(weighted_brightness,2)
        result["contrastRetention"]=round(max(0.0,100.0-(weighted_contrast/max(original_contrast,1e-6))*100),1)
    if reference and reference.get("dominantColors"):
        predictions=[row[7] for row in rows]
        reference_total=sum(item["weight"] for item in reference["dominantColors"]) or 1.0
        error=sum((item["weight"]/reference_total)*min(dist(item["color"],color) for color in predictions)
                  for item in reference["dominantColors"])
        result["referenceSimilarityScore"]=round(max(0.0,100.0-error*2.2),1)
        result["referenceEstimatedDeltaE"]=round(error,2)
    mixed_weight=sum(weights[row[0]] for row in rows if row[3]=="MIX")/total
    confidence=94.0-estimated*1.15-mixed_weight*13
    if not reference or not reference.get("dominantColors"):
        confidence-=8
    if any(row[3]=="MIX" and len(row[5].split(","))>2 for row in rows):
        confidence-=5
    result["confidenceScore"]=round(max(0.0,min(100.0,confidence)),1)
    result["confidenceLabel"]="High" if result["confidenceScore"]>=78 else ("Medium" if result["confidenceScore"]>=55 else "Low")
    result["mixModel"]=mix_model
    return result

def printability_metrics(rows, usage, real_count, output_count, layouts, project):
    weights={slot:float(usage.get(slot,0)) for slot,*_ in rows}
    total=sum(weights.values()) or 1.0
    mixed_rows=[row for row in rows if row[3]=="MIX"]
    used_mixed_slots=sorted({row[1] for row in mixed_rows})
    mixed_share=sum(weights.get(row[0],0.0) for row in mixed_rows)/total
    purge_values=[]
    for key,(kind,width) in layouts.items():
        if kind=="matrix" and isinstance(project.get(key),list):
            block=[float(value) for value in project[key][:output_count*output_count]]
            purge_values.extend(value for index,value in enumerate(block)
                                if index//output_count != index%output_count)
            break
    purge_mean=sum(purge_values)/len(purge_values) if purge_values else None
    complexity_score=(len(used_mixed_slots)*5 + mixed_share*40 + max(0,real_count-2)*7)
    difficulty="Low" if complexity_score<38 else ("Medium" if complexity_score<68 else "High")
    suggestions=[]
    if len(used_mixed_slots)>10:
        suggestions.append("For fewer generated mix slots, turn off Smart quality and lower Quality vs waste, or switch Planner to Fast for a simpler pass.")
    if mixed_share>0.55:
        suggestions.append("Most painted usage is mixed; run a small calibration print before committing material.")
    if real_count<DEFAULT_AUTO_MAX_REAL_SLOTS and len(used_mixed_slots)>4:
        suggestions.append("Try a higher Physical slots value or a broader Filament source; closer anchors can reduce mixed regions and purge risk.")
    elif real_count>=DEFAULT_AUTO_MAX_REAL_SLOTS and real_count<MAX_REAL_SLOTS and len(used_mixed_slots)>4:
        suggestions.append("Choose 7 exp or 8 exp only when you do not need the support-material slot; otherwise add closer filament colors.")
    if real_count>DEFAULT_AUTO_MAX_REAL_SLOTS:
        suggestions.append("This is an experimental high-fidelity physical-slot plan; verify support-material slot needs before printing.")
    return {
        "physicalSlots":real_count,
        "mixedSlots":len(used_mixed_slots),
        "paintedMixedShare":round(mixed_share*100,1),
        "purgeTransitionMean":round(purge_mean,1) if purge_mean is not None else None,
        "difficulty":difficulty,
        "swapRisk":"High" if mixed_share>.55 else ("Medium" if used_mixed_slots else "Low"),
        "filamentUsageEstimate":None,
        "printTimeEstimate":None,
        "sliceRequiredForTimeAndUsage":True,
        "recommendations":suggestions,
    }

def candidate_palette(palette_source, inventory, custom_catalog_path, material_families=None):
    if palette_source=="inventory":
        return filter_material_families(inventory_palette(inventory), material_families)
    if palette_source=="custom":
        return custom_palette(custom_catalog_path)
    if palette_source=="exact-cmykw":
        return []
    return catalog_palette("all" if palette_source=="all-bambu" else "core",inventory,material_families)

def additional_anchor_recommendation(old_colors, usage, anchors, palette_source, inventory,
                                     custom_catalog_path, quality_bias, mix_model, current_quality,
                                     planner_mode="best", material_families=None):
    if len(anchors)>=MAX_REAL_SLOTS or palette_source=="exact-cmykw":
        return None
    selected={anchor_color(anchor) for anchor in anchors}
    best=None
    for candidate in candidate_palette(palette_source,inventory,custom_catalog_path,material_families):
        if anchor_color(candidate) in selected:
            continue
        trial=anchors+[candidate]
        newc,_,_,_,_,rows=build_palette(old_colors,trial,usage,quality_bias,mix_model,planner_mode)
        metrics=quality_metrics(rows,usage,old_colors,None,mix_model)
        mix_count=len({row[1] for row in rows if row[3]=="MIX"})
        gain=current_quality["estimatedDeltaE"]-metrics["estimatedDeltaE"]
        score=gain*3-mix_count*0.02
        if best is None or score>best[0]:
            best=(score,candidate,gain,mix_count,len(newc),metrics)
    if best is None or best[2]<0.25:
        return None
    _,candidate,gain,mix_count,_,metrics=best
    return {
        "key":anchor_key(candidate),
        "name":anchor_name(candidate),
        "series":str(candidate.get("series") or filament_family(anchor_name(candidate))).strip(),
        "color":anchor_color(candidate),
        "estimatedDeltaEReduction":round(gain,2),
        "estimatedQualityScore":metrics["qualityScore"],
        "estimatedMixedSlots":mix_count,
        "availability":(
            "owned, only if support slot is free"
            if palette_source=="inventory" and len(anchors)>=DEFAULT_AUTO_MAX_REAL_SLOTS else
            "owned"
            if palette_source=="inventory" else
            "confirm in selected catalog region; only if support slot is free"
            if len(anchors)>=DEFAULT_AUTO_MAX_REAL_SLOTS else
            "confirm in selected catalog region"
        ),
    }

def recipe_items_from_rows(rows, anchors):
    recipes=[]
    for old_slot,new_slot,target,kind,label,component_ids,ratio_text,preview,error,direct_error,gain in rows:
        available_grams=None
        component_slots=[int(value) for value in component_ids.split(",") if value]
        if kind=="MIX" and component_slots and all(anchors[slot-1]["remainingGrams"] is not None for slot in component_slots):
            component_ratios=[float(value) for value in ratio_text.split(",")]
            available_grams=round(min(anchors[slot-1]["remainingGrams"]/ratio
                                      for slot,ratio in zip(component_slots,component_ratios)),1)
        recipes.append({
            "oldSlot":old_slot,
            "newSlot":new_slot,
            "targetColor":target,
            "kind":kind,
            "label":label or f"Mixed slot {new_slot}",
            "components":component_ids,
            "ratios":ratio_text,
            "preview":preview,
            "deltaE":float(error),
            "directDeltaE":float(direct_error),
            "visualGain":float(gain),
            "availableGrams":available_grams,
        })
    return recipes

def plan_preview_payload(infile, mode, palette_source, planner_mode, planning_sample,
                         catalog_region, region_label, catalog_source_label, oldn,
                         real_count, newc, rows, anchors, real_profiles, quality_bias,
                         quality_bias_mode, quality, printability, recommendation,
                         reference_result, imported, warnings, material_families=None,
                         pinned_anchor_keys=None):
    return {
        "type":"planPreview",
        "input":str(infile),
        "filename":infile.name,
        "mode":mode,
        "paletteSource":palette_source,
        "plannerMode":planner_mode,
        "planningSample":planning_sample,
        "catalogRegion":catalog_region,
        "catalogRegionLabel":region_label,
        "catalogSource":catalog_source_label,
        "materialFamilies":material_families or [],
        "pinnedAnchorKeys":pinned_anchor_keys or [],
        "sourceSlots":oldn,
        "realSlots":real_count,
        "outputSlots":len(newc),
        "qualityBias":quality_bias,
        "qualityBiasMode":quality_bias_mode,
        "quality":quality,
        "printability":printability,
        "recommendation":recommendation,
        "reference":reference_result,
        "import":imported,
        "warnings":warnings,
        "anchors":[
            {
                "key":anchor_key(anchor),
                "slot":i+1,
                "name":anchor_name(anchor),
                "series":str(anchor.get("series") or filament_family(anchor_name(anchor))).strip(),
                "color":anchor_color(anchor),
                "preset":real_profiles[i][0],
                "filamentID":real_profiles[i][1],
                "remainingGrams":anchor["remainingGrams"],
            }
            for i,anchor in enumerate(anchors)
        ],
        "recipes":recipe_items_from_rows(rows,anchors),
    }

def smart_quality_plan_score(metrics, rows, usage, real_count, output_count, quality_bias):
    mixed_slots,mixed_share,weak_share=palette_usage_stats(rows,usage,quality_bias)
    practical_pressure=(100-clamp_quality_bias(quality_bias))/100
    return (
        metrics["estimatedDeltaE"]*2.4
        + metrics["maximumDeltaE"]*PALETTE_MAX_ERROR_WEIGHT
        + mixed_slots*(0.16+0.18*practical_pressure)
        + mixed_share*(1.1+0.8*practical_pressure)
        + real_count*0.18
        + max(0,output_count-real_count)*0.04
        + weak_share*5.0
        - metrics.get("contrastRetention",0)*0.004
    )

def smart_quality_followups(summary, mode):
    if summary["qualityBias"] >= 95:
        return []
    if summary["estimatedDeltaE"] <= 0.05 and summary["maximumDeltaE"] <= 0.10 and summary["mixedSlots"] == 0:
        return []
    too_far=summary["estimatedDeltaE"] > 3.2 or summary["maximumDeltaE"] > 11.5 or summary["qualityScore"] < 88
    too_wasteful=summary["outputSlots"] > 25 or summary["paintedMixedShare"] > 72
    very_clean=summary["estimatedDeltaE"] <= 1.4 and summary["maximumDeltaE"] <= 7.5
    if mode=="cmykw":
        if too_far:
            return [85,100]
        return [50,85]
    if too_far and summary["maximumDeltaE"] > 18:
        return [100]
    if too_far and too_wasteful:
        return [100,50]
    if too_far:
        return [100,85]
    if too_wasteful or very_clean:
        return [50,35]
    return [50,85]

def append_unique_quality(queue, seen, values, allowed=None):
    allowed=set(allowed or SMART_QUALITY_CANDIDATES)
    for value in values:
        value=int(value)
        if value in allowed and value not in seen and value not in queue:
            queue.append(value)

def select_smart_palette(old_colors, usage, mode, inventory, palette_source, real_slots="auto",
                         custom_catalog_path=None, reference=None, mix_model="bambu", planner_mode="best",
                         progress=None, material_families=None, pinned_anchor_keys=None):
    planner_mode=normalize_planner_mode(planner_mode)
    candidates=list(SMART_QUALITY_CANDIDATES)
    if mode=="cmykw":
        candidates=sorted(set(candidates+[75,90]))
    best=None
    summaries=[]
    errors=[]
    skipped=[]
    evaluated=set()
    queue=[SMART_QUALITY_PROBE if SMART_QUALITY_PROBE in candidates else candidates[len(candidates)//2]]
    max_candidates=4 if mode!="cmykw" else 5
    attempt_index=0
    while queue and attempt_index < max_candidates:
        quality_bias=queue.pop(0)
        if quality_bias in evaluated:
            continue
        evaluated.add(quality_bias)
        try:
            start_progress=0.22 + 0.10 * (attempt_index / max_candidates)
            done_progress=0.22 + 0.10 * ((attempt_index + 1) / max_candidates)
            if progress:
                cache_note=" with cached Bambu mix recipes" if planner_is_best(planner_mode) else ""
                progress(
                    start_progress,
                    f"{planner_mode.title()} adaptive spectrum testing quality {quality_bias}/100{cache_note}"
                )
            anchors=select_anchors(
                old_colors,usage,mode,inventory,palette_source,real_slots,
                custom_catalog_path,reference,mix_model,quality_bias,planner_mode,
                material_families,pinned_anchor_keys
            )
            palette=build_palette(old_colors,anchors,usage,quality_bias,mix_model,planner_mode)
            rows=palette[-1]
            metrics=quality_metrics(rows,usage,old_colors,reference,mix_model)
            mixed_slots,mixed_share,_=palette_usage_stats(rows,usage,quality_bias)
            output_count=len(palette[0])
            score=smart_quality_plan_score(metrics,rows,usage,len(anchors),output_count,quality_bias)
            summary={
                "qualityBias":quality_bias,
                "realSlots":len(anchors),
                "outputSlots":output_count,
                "mixedSlots":mixed_slots,
                "paintedMixedShare":round(mixed_share*100,1),
                "estimatedDeltaE":metrics["estimatedDeltaE"],
                "maximumDeltaE":metrics["maximumDeltaE"],
                "qualityScore":metrics["qualityScore"],
                "score":round(score,3),
            }
            summaries.append(summary)
            if progress:
                progress(
                    done_progress,
                    f"Quality {quality_bias}/100 candidate: {len(anchors)} physical, {mixed_slots} mixed, mean Delta E {metrics['estimatedDeltaE']:.2f}"
                )
            if best is None or score<best["score"]:
                best={
                    "score":score,
                    "qualityBias":quality_bias,
                    "anchors":anchors,
                    "palette":palette,
                    "metrics":metrics,
                    "summaries":summaries,
                }
            if metrics["estimatedDeltaE"] <= 0.05 and metrics["maximumDeltaE"] <= 0.10 and mixed_slots == 0:
                if progress:
                    progress(done_progress, "Smart planner found a perfect no-mix palette; skipping heavier candidates")
                break
            append_unique_quality(queue,evaluated,smart_quality_followups(summary,mode),candidates)
        except Exception as error:
            errors.append(f"{quality_bias}: {error}")
            append_unique_quality(queue,evaluated,[85,50,100],candidates)
        attempt_index+=1
    skipped=[quality for quality in candidates if quality not in evaluated]
    if best is None:
        detail="; ".join(errors[-3:]) if errors else "no candidate plans were generated"
        raise RuntimeError("Smart quality planning failed: " + detail)
    best["summaries"]=summaries
    best["skippedQualityCandidates"]=skipped
    best["smartSearchMode"]="adaptive-spectrum"
    return best

def expected_remapped_paint_counts(source_counts, slot_map, oldn, newn):
    expected=Counter()
    for code,count in source_counts.items():
        mapped,_=remap_paint_code(code,slot_map,oldn,newn)
        expected[mapped]+=count
    return expected

def analysis_preview_colors(output_colors, rows, real_count):
    errors=defaultdict(list)
    anchor_for_slot={}
    for row in rows:
        errors[row[1]].append(float(row[8]))
        if row[3]=="ANCHOR":
            anchor_for_slot[row[1]]=row[1]
        else:
            components=[int(value) for value in row[5].split(",") if value]
            if components:
                anchor_for_slot[row[1]]=components[0]
    heat=[heatmap_color(max(errors.get(slot,[0.0]))) for slot in range(1,len(output_colors)+1)]
    influence_palette=["#28B8D5","#E86C8C","#EDC949","#4E79A7","#59A14F","#B07AA1"]
    influence=[influence_palette[(anchor_for_slot.get(slot,min(slot,real_count))-1)%len(influence_palette)]
               for slot in range(1,len(output_colors)+1)]
    return heat,influence

def remap_paint_codes_by_codec(tmp, old_slot_to_new_slot, oldn, newn):
    patched=[]
    cache={}
    for p in sorted((tmp/"3D"/"Objects").rglob("*.model")):
        if not p.is_file(): continue
        replacement=p.with_suffix(".model.patched")
        changed=False
        try:
            with p.open("rb") as source, replacement.open("wb") as output:
                for text in source:
                    def repl(m):
                        nonlocal changed
                        code=m.group(3).decode("ascii",errors="replace").upper()
                        if code not in cache:
                            cache[code], _=remap_paint_code(code, old_slot_to_new_slot, oldn, newn)
                        mapped=m.group(1)+m.group(2)+cache[code].encode("ascii")+m.group(2)
                        changed=changed or mapped != m.group(0)
                        return mapped
                    output.write(PAINT_BYTES_VALUE_PATTERN.sub(repl,text))
            if changed:
                replacement.replace(p)
                patched.append(p.relative_to(tmp).as_posix())
            else:
                replacement.unlink()
        except Exception:
            if replacement.exists():
                replacement.unlink()
            raise
    return patched

def remap_model_setting_extruders(tmp, old_slot_to_new_slot):
    path=tmp/"Metadata"/"model_settings.config"
    if not path.exists():
        return 0
    tree=ET.parse(path)
    changed=0
    for metadata in tree.getroot().iter("metadata"):
        if metadata.get("key") != "extruder":
            continue
        old_slot=int(metadata.get("value","0"))
        new_slot=old_slot_to_new_slot.get(old_slot,old_slot)
        if new_slot != old_slot:
            metadata.set("value",str(new_slot))
            changed+=1
    if changed:
        ET.indent(tree,space="  ")
        tree.write(path,encoding="UTF-8",xml_declaration=True)
    return changed

def model_setting_extruder_slots(tmp, slot_count):
    path=tmp/"Metadata"/"model_settings.config"
    if not path.exists():
        return set()
    try:
        root=ET.parse(path).getroot()
    except (ET.ParseError,OSError) as exc:
        raise RuntimeError("Could not read source object filament assignments") from exc
    slots=set()
    for metadata in root.iter("metadata"):
        if metadata.get("key") != "extruder":
            continue
        try:
            slot=int(metadata.get("value","0"))
        except ValueError as exc:
            raise RuntimeError("Source object has an invalid extruder assignment") from exc
        if slot == 0:
            continue
        if slot < 0 or slot > slot_count:
            raise RuntimeError(f"Source object references missing extruder slot {slot}")
        slots.add(slot)
    return slots

def include_model_extruder_usage(paint_usage, extruder_slots):
    usage=Counter(paint_usage or {})
    marker=max(1.0,sum(usage.values())*MODEL_EXTRUDER_USAGE_FRACTION)
    for slot in extruder_slots:
        if usage.get(slot,0) <= 0:
            usage[slot]=marker
    return usage

NONPREFIX_FILAMENT_ARRAY_KEYS = {
    "activate_air_filtration",
    "additional_cooling_fan_speed",
    "additional_fan_full_speed_layer",
    "chamber_temperatures",
    "circle_compensation_speed",
    "close_additional_fan_first_x_layers",
    "close_fan_the_first_x_layers",
    "complete_print_exhaust_fan_speed",
    "cool_plate_temp",
    "cool_plate_temp_initial_layer",
    "cooling_perimeter_transition_distance",
    "cooling_slowdown_logic",
    "counter_coef_1",
    "counter_coef_2",
    "counter_coef_3",
    "counter_limit_max",
    "counter_limit_min",
    "diameter_limit",
    "during_print_exhaust_fan_speed",
    "enable_overhang_bridge_fan",
    "enable_pressure_advance",
    "eng_plate_temp",
    "eng_plate_temp_initial_layer",
    "fan_cooling_layer_time",
    "fan_max_speed",
    "fan_min_speed",
    "first_x_layer_fan_speed",
    "first_x_layer_part_fan_speed",
    "flush_volumes_matrix",
    "flush_volumes_vector",
    "full_fan_speed_layer",
    "hole_coef_1",
    "hole_coef_2",
    "hole_coef_3",
    "hole_limit_max",
    "hole_limit_min",
    "hot_plate_temp",
    "hot_plate_temp_initial_layer",
    "impact_strength_z",
    "ironing_fan_speed",
    "long_retractions_when_ec",
    "no_slow_down_for_cooling_on_outwalls",
    "nozzle_temperature",
    "nozzle_temperature_initial_layer",
    "nozzle_temperature_range_high",
    "nozzle_temperature_range_low",
    "overhang_fan_speed",
    "overhang_fan_threshold",
    "overhang_threshold_participating_cooling",
    "override_process_overhang_speed",
    "pre_start_fan_time",
    "pressure_advance",
    "reduce_fan_stop_start_freq",
    "required_nozzle_hrc",
    "retraction_distances_when_ec",
    "slow_down_for_layer_cooling",
    "slow_down_layer_time",
    "slow_down_min_speed",
    "supertack_plate_temp",
    "supertack_plate_temp_initial_layer",
    "temperature_vitrification",
    "textured_plate_temp",
    "textured_plate_temp_initial_layer",
    "volumetric_speed_coefficients",
}

def looks_filament_related(key):
    k=key.lower()
    if k in NONPREFIX_FILAMENT_ARRAY_KEYS:
        return True
    if any(x in k for x in ["object","mesh","vertex","triangle","model","plate_list","build_item"]): return False
    if k.startswith("filament_"): return True
    return any(t in k for t in ["fan","cooling","temperature","temp","chamber","pressure_advance","purge","flush_volumes","nozzle","flow_ratio","density","shrink"])

def resize_linear(v,n,default=""):
    v=list(v) if isinstance(v,list) else []
    if len(v)<n:
        fill=v[-1] if v else default
        return v+[fill]*(n-len(v))
    if len(v)>n: return v[:n]
    return v

def remap_slot_blocks(v,oldn,representatives,width,default=""):
    v=list(v) if isinstance(v,list) else []
    blocks=[v[i*width:(i+1)*width] for i in range(oldn)]
    fill=[default]*width
    return [value for slot in representatives for value in (blocks[slot-1] if slot<=len(blocks) else fill)]

def nearest_nonzero_transition(source,oldn,old_colors,from_color,to_color):
    candidates=[]
    for row in range(oldn):
        for column in range(oldn):
            value=source[row*oldn+column]
            if row != column and float(value) != 0.0:
                error=dist(from_color,old_colors[row])+dist(to_color,old_colors[column])
                candidates.append((error,value))
    if not candidates:
        raise RuntimeError("Source purge matrix does not contain a non-zero transition for new filament pairs")
    return min(candidates,key=lambda candidate:candidate[0])[1]

def remap_square_blocks(v,oldn,representatives,blocks,old_colors,new_colors):
    v=list(v) if isinstance(v,list) else []
    size=oldn*oldn
    output=[]
    for index in range(blocks):
        source=v[index*size:(index+1)*size]
        for new_row,row in enumerate(representatives):
            for new_column,column in enumerate(representatives):
                value=source[(row-1)*oldn+(column-1)]
                if new_row != new_column and float(value) == 0.0:
                    value=nearest_nonzero_transition(
                        source,oldn,old_colors,new_colors[new_row],new_colors[new_column]
                    )
                output.append(value)
    return output

def off_diagonal_zero_count(values,n,blocks):
    count=0
    size=n*n
    for block in range(blocks):
        source=values[block*size:(block+1)*size]
        for row in range(n):
            for column in range(n):
                if row != column and float(source[row*n+column]) == 0.0:
                    count+=1
    return count

def filament_array_layouts(obj,oldn):
    layouts={}
    if oldn <= 0:
        return layouts
    for key,value in obj.items():
        if not isinstance(value,list) or not looks_filament_related(key):
            continue
        length=len(value)
        lk=key.lower()
        if ("purging_volumes_matrix" in lk or "flush_volumes_matrix" in lk or "flush_matrix" in lk) and length % (oldn*oldn) == 0:
            blocks=length//(oldn*oldn)
            if blocks in (1,2,4):
                layouts[key]=("matrix",blocks)
        elif length % oldn == 0:
            width=length//oldn
            if width in (1,2,4):
                layouts[key]=("slot",width)
    return layouts

def resize_project_filament_arrays(obj,oldn,representatives,layouts,old_colors,new_colors):
    newn=len(representatives)
    for key,(kind,width) in layouts.items():
        value=obj.get(key,[])
        if key=="filament_self_index" and kind=="slot":
            obj[key]=[str(slot) for slot in range(1,newn+1) for _ in range(width)]
        elif kind=="matrix":
            obj[key]=remap_square_blocks(value,oldn,representatives,width,old_colors,new_colors)
        else:
            obj[key]=remap_slot_blocks(value,oldn,representatives,width)

def ensure_list(obj,key,n,default):
    obj[key]=resize_linear(obj.get(key,[]),n,default)

def validate_arrays(obj,newn,real_count,layouts,source_off_diagonal_zeros=None):
    if real_count < MIN_REAL_SLOTS or real_count > MAX_REAL_SLOTS or newn < real_count:
        raise RuntimeError("Output physical filament slot count is invalid")
    keys=["filament_colour","filament_settings_id","filament_ids","filament_is_mixed","filament_mixed_components","filament_mixed_sublayer_ratios","filament_multi_colour","default_filament_colour"]
    for key in keys:
        if not isinstance(obj.get(key),list) or len(obj[key])!=newn:
            raise RuntimeError(f"Array length mismatch {key}: expected {newn}")
    for key,(kind,width) in layouts.items():
        expected=width*newn*newn if kind=="matrix" else width*newn
        if not isinstance(obj.get(key),list) or len(obj[key])!=expected:
            raise RuntimeError(f"Filament array length mismatch {key}: expected {expected}")
        if kind=="matrix":
            output_count=off_diagonal_zero_count(obj[key],newn,width)
            if output_count:
                raise RuntimeError(f"Purge matrix {key} contains {output_count} zero off-diagonal transitions")
    for i in range(real_count):
        if obj["filament_is_mixed"][i]!="0":
            raise RuntimeError(f"Real slot {i+1} marked mixed")
        if obj["filament_mixed_components"][i].strip() or obj["filament_mixed_sublayer_ratios"][i].strip():
            raise RuntimeError(f"Real slot {i+1} has mixed-filament data")
    for i in range(real_count,newn):
        if obj["filament_is_mixed"][i]!="1": raise RuntimeError(f"Mixed slot {i+1} not marked mixed")
        cs=[int(x) for x in obj["filament_mixed_components"][i].split(",") if x.strip()]
        rs=[float(x) for x in obj["filament_mixed_sublayer_ratios"][i].split(",") if x.strip()]
        if len(cs)<2 or len(cs)!=len(rs): raise RuntimeError(f"Mixed slot {i+1} component/ratio mismatch")
        if len(set(cs))!=len(cs): raise RuntimeError(f"Mixed slot {i+1} repeats a component")
        if any(c<1 or c>real_count for c in cs): raise RuntimeError(f"Mixed slot {i+1} refs non-real slot {cs}")
        if i+1 in cs: raise RuntimeError(f"Mixed slot {i+1} references itself")
        if any(obj["filament_is_mixed"][c-1]!="0" for c in cs): raise RuntimeError(f"Mixed slot {i+1} references another mixed slot")
        if any(r<=0 or r>=1 for r in rs) or abs(sum(rs)-1)>0.01:
            raise RuntimeError(f"Mixed slot {i+1} ratios are invalid")

def validate_bambu_color_sync(obj, real_count):
    colors=[hx(value) for value in obj.get("filament_colour",[])]
    multi=[hx(value) for value in obj.get("filament_multi_colour",[])]
    if len(colors) != len(multi) or colors != multi:
        raise RuntimeError("filament_colour and filament_multi_colour are not synchronized")
    reconstructed=preview_colors_from_project(obj)
    entries=[]
    for index in range(real_count,len(colors)):
        expected=reconstructed[index]
        stored=colors[index]
        stored_multi=multi[index] if index < len(multi) else ""
        delta=dist(stored,expected)
        entries.append({
            "slot":index+1,
            "exported":stored,
            "bambuLoaded":expected,
            "deltaE":round(delta,2),
            "components":obj["filament_mixed_components"][index],
            "ratios":obj["filament_mixed_sublayer_ratios"][index],
        })
        if stored != expected or stored_multi != expected:
            raise RuntimeError(
                f"Mixed slot {index+1} color is not Bambu-reconstructed: "
                f"saved {stored}/{stored_multi}, expected {expected}"
            )
    return {
        "predictionModel":"Bambu Studio FilamentMixer pigment reconstruction",
        "verified":True,
        "maximumDeltaE":round(max((entry["deltaE"] for entry in entries),default=0.0),2),
        "entries":entries,
    }

def validate_output_archive(outfile,newn,real_count,layouts,source_off_diagonal_zeros=None,
                            preservation=None, expected_paint_counts=None):
    with zipfile.ZipFile(outfile) as archive:
        validated_archive_infos(archive)
        psrel=find_project_settings(archive.namelist())
        if not psrel:
            raise RuntimeError("Written archive has no project_settings.config")
        obj,_=json.JSONDecoder().raw_decode(archive.read(psrel).decode("utf-8", errors="replace").lstrip())
        validate_arrays(obj,newn,real_count,layouts,source_off_diagonal_zeros)
        color_validation=validate_bambu_color_sync(obj,real_count)
        paint_codes, paint_counts=collect_archive_paint_codes(archive)
        if expected_paint_counts is not None and paint_counts != expected_paint_counts:
            raise RuntimeError("Paint remap validation failed: output states differ from the decoded expected mapping")
        usage=paint_slot_usage(paint_counts,newn)
        model_settings=next((n for n in archive.namelist() if n.lower().endswith("metadata/model_settings.config")),None)
        if model_settings:
            root=ET.fromstring(archive.read(model_settings))
            for metadata in root.iter("metadata"):
                if metadata.get("key") == "extruder":
                    slot=int(metadata.get("value","0"))
                    if slot == 0:
                        continue
                    if slot < 0 or slot > newn:
                        raise RuntimeError(f"Object metadata references missing extruder slot {slot}")
        preservation_result=verify_preservation(archive,preservation) if preservation else None
        if preservation_result is not None:
            preservation_result["paintRemapVerified"]=expected_paint_counts is not None
    return paint_codes, usage, preservation_result, color_validation

def convert(infile, mode, palette_source="inventory", output_dir=None, reveal=True, real_slots="auto",
            reference=None, custom_catalog_path=None, quality_bias=DEFAULT_QUALITY_BIAS,
            mix_model="bambu", analysis_dir=None, texture_override=None,
            internal_colors=48, catalog_region="global", planner_mode="best",
            planning_sample="paint", plan_only=False, material_families=None,
            pinned_anchor_keys=None, progress=lambda fraction,message: None):
    infile=Path(infile).expanduser().resolve()
    planner_mode=normalize_planner_mode(planner_mode)
    planning_sample=normalize_planning_sample(planning_sample)
    material_families=normalize_material_families(material_families)
    pinned_anchor_keys=normalize_anchor_keys(pinned_anchor_keys)
    quality_bias_mode="auto" if is_auto_quality_bias(quality_bias) else "manual"
    quality_bias=DEFAULT_QUALITY_BIAS if quality_bias_mode=="auto" else clamp_quality_bias(quality_bias)
    catalog_region=str(catalog_region or "global").strip().lower()
    region_label=catalog_region_label(catalog_region)
    if mix_model not in MIX_MODELS:
        raise RuntimeError(f"Unknown mixed-color prediction model {mix_model!r}")
    downloads=Path(output_dir).expanduser().resolve() if output_dir else Path.home()/"Downloads"
    downloads.mkdir(parents=True,exist_ok=True)
    suffix="CMYKW" if mode=="cmykw" else "OFFICIAL_BAMBU_DERIVED"
    outfile=downloads/f"{infile.stem}_FullSpectrum_{suffix}_{OUTPUT_VERSION}.3mf"
    csvfile=downloads/f"{infile.stem}_FullSpectrum_{suffix}_{OUTPUT_VERSION}_recipe.csv"
    report=downloads/f"{infile.stem}_FullSpectrum_{suffix}_{OUTPUT_VERSION}_report.txt"
    color_report=downloads/f"{infile.stem}_FullSpectrum_{suffix}_{OUTPUT_VERSION}_COLOR_VALIDATION.md"
    tmp=Path(tempfile.mkdtemp(prefix="fullspectrum_"))
    reference_tmp=Path(tempfile.mkdtemp(prefix="fsreference_"))
    import_tmp=Path(tempfile.mkdtemp(prefix="fsimport_"))
    staged_outfile=outfile.with_suffix(outfile.suffix+".tmp")
    warnings=[]
    imported=None
    project_file=infile
    catalog_source_label=None
    try:
        progress(0.04,f"Opening {infile.name}")
        if infile.suffix.lower() in (".obj",".glb"):
            progress(0.06,f"Importing textured {infile.suffix[1:].upper()} geometry, UV mapping and texture colors")
            project_file=import_tmp/f"{infile.stem}_painted_source.3mf"
            imported=(import_obj_project(infile,project_file,import_tmp,texture_override,internal_colors,progress)
                      if infile.suffix.lower()==".obj"
                      else import_glb_project(infile,project_file,import_tmp,internal_colors,progress))
            if imported["compressedForBambu"]:
                warnings.append(
                    f"Extended analysis found {imported['internalColorCount']} source clusters; "
                    f"paint export was compressed to {imported['exportColorCount']} Bambu-compatible colors."
                )
            if reference is None:
                reference=str(infile)
        elif infile.suffix.lower() in (".png",".jpg",".jpeg"):
            raise RuntimeError("An image supplies color reference but has no printable geometry. Add it as a reference to a painted 3MF or textured OBJ.")
        elif infile.suffix.lower()!=".3mf":
            raise RuntimeError("Input must be a painted 3MF or an experimental textured OBJ/GLB import")
        minimum_inventory=4 if mode=="cmykw" else (MIN_REAL_SLOTS if str(real_slots)=="auto" else int(real_slots))
        inventory=read_bambu_inventory(required=palette_source=="inventory",minimum_colors=minimum_inventory)
        if palette_source=="inventory":
            progress(0.12,f"Loaded {inventory['usableCount']} locally available PLA spools")
        elif palette_source=="exact-cmykw":
            progress(0.12,"Using exact CMYKW physical filament colors")
        elif palette_source=="custom":
            progress(0.12,"Using user supplied filament library")
        else:
            catalog_options=catalog_palette('all' if palette_source=='all-bambu' else 'core',inventory,material_families)
            catalog_source_label=next((item.get("catalogSource") for item in catalog_options if item.get("catalogSource")),None)
            progress(0.12,f"Using {len(catalog_options)} Bambu Lab planning colors from Bambu Studio catalog data")
            warnings.append(
                f"Catalog colors are planning choices for {region_label}. "
                "FullSpectrum does not check live store stock; verify availability before buying filament."
            )
        progress(0.14,"Extracting and scanning source 3MF archive")
        with zipfile.ZipFile(project_file) as z:
            names=z.namelist()
            safe_extract_archive(z,tmp)
        psrel=find_project_settings(names)
        if not psrel: raise RuntimeError("No project_settings.config found")
        pspath=tmp/psrel
        obj=read_json_config(pspath)
        old=colors_from_project(obj); oldn=len(old)
        if not old: raise RuntimeError("No filament_colour array found")
        progress(0.17,"Fingerprinting source geometry and paint data")
        preservation=preservation_snapshot(tmp,psrel)
        reference_result=analyze_reference(reference,reference_tmp) if reference else None
        progress(0.19,"Collecting existing Bambu paint states")
        ordered_codes, code_counts=collect_paint_codes(tmp)
        paint_usage=paint_slot_usage(code_counts, oldn)
        object_extruders=model_setting_extruder_slots(tmp,oldn)
        paint_usage=include_model_extruder_usage(paint_usage,object_extruders)
        usage=paint_usage
        if planning_sample=="preview":
            progress(0.205,"Sampling optimized preview mesh for visual color weighting")
            with zipfile.ZipFile(project_file) as preview_archive:
                preview_usage=preview_slot_usage(preview_archive,oldn)
            if preview_usage:
                usage=blend_preview_usage(paint_usage,preview_usage)
                warnings.append(
                    "Planner used optimized preview-mesh color weighting. "
                    "The final 3MF still remaps the original Bambu paint states exactly."
                )
                progress(0.215,f"Preview sample found {len(preview_usage)} visible painted slots")
            else:
                warnings.append(
                    "Preview-weighted planning was requested, but no preview color sample could be built; "
                    "falling back to original paint-state usage."
                )
                planning_sample="paint"
        layouts=filament_array_layouts(obj,oldn)
        source_off_diagonal_zeros={
            key:off_diagonal_zero_count(obj[key],oldn,width)
            for key,(kind,width) in layouts.items() if kind=="matrix"
        }

        source_label={
            "inventory":"available inventory",
            "catalog":"the Bambu catalog",
            "all-bambu":"the extended Bambu planning catalog",
            "custom":"a custom filament library",
            "exact-cmykw":"exact CMYKW roles",
        }[palette_source]
        smart_candidates=[]
        smart_search_mode=None
        skipped_quality_candidates=[]
        if quality_bias_mode=="auto":
            progress(0.22,f"Testing smart quality/waste plans with the {planner_mode} planner")
            plan=select_smart_palette(
                old,usage,mode,inventory,palette_source,real_slots,
                custom_catalog_path,reference_result,mix_model,planner_mode,progress,
                material_families,pinned_anchor_keys
            )
            quality_bias=plan["qualityBias"]
            anchors=plan["anchors"]
            newc,ism,comps,ratios,old_slot_to_new_slot,rows=plan["palette"]
            smart_candidates=plan["summaries"]
            smart_search_mode=plan.get("smartSearchMode")
            skipped_quality_candidates=plan.get("skippedQualityCandidates",[])
            progress(
                0.34,
                f"Smart plan selected quality {quality_bias}/100 with {len(anchors)} physical anchors and {len(newc)-len(anchors)} mixed slots",
            )
        else:
            progress(0.22,f"Generating {planner_mode} anchors from painted colors and " + source_label)
            anchors=select_anchors(old, usage, mode, inventory, palette_source,real_slots,
                                   custom_catalog_path,reference_result,mix_model,quality_bias,planner_mode,
                                   material_families,pinned_anchor_keys)
            progress(0.34,"Building mixes with useful predicted visual gain")
            newc,ism,comps,ratios,old_slot_to_new_slot,rows=build_palette(
                old,anchors,usage,quality_bias,mix_model,planner_mode
            )
        real_count=len(anchors)
        newn=len(newc)
        if real_count > DEFAULT_AUTO_MAX_REAL_SLOTS:
            warnings.append(
                f"Experimental {real_count}-physical-slot plan: this can improve color fidelity, "
                "but may consume the slot normally reserved for support material."
            )
        if newn > MAX_BAMBU_PAINT_SLOT:
            raise RuntimeError(f"Output requires {newn} slots, but Bambu paint_color supports only {MAX_BAMBU_PAINT_SLOT}")
        quality=quality_metrics(rows,usage,old,reference_result,mix_model)
        quality["resolvedQualityBias"]=quality_bias
        quality["qualityBiasMode"]=quality_bias_mode
        quality["plannerMode"]=planner_mode
        quality["planningSample"]=planning_sample
        if smart_candidates:
            quality["smartCandidates"]=smart_candidates
        if smart_search_mode:
            quality["smartSearchMode"]=smart_search_mode
            quality["skippedQualityCandidates"]=skipped_quality_candidates
        printability=printability_metrics(rows,usage,real_count,newn,layouts,obj)
        mix_limit=quality_mix_limit(quality_bias)
        unmatched=[
            row for row in rows
            if usage.get(row[0],0)>0 and float(row[8])>mix_limit
        ]
        if unmatched:
            warnings.append(
                f"{len(unmatched)} painted colors have no reliable match within Delta E "
                f"{mix_limit:.0f} at quality {quality_bias}; nearest physical colors were kept instead "
                "of creating misleading mixed recipes. Add closer filament colors for these regions."
            )
        recommendation=additional_anchor_recommendation(
            old,usage,anchors,palette_source,inventory,custom_catalog_path,
            quality_bias,mix_model,quality,planner_mode,material_families
        )
        if recommendation:
            printability["recommendations"].append(
                f"Consider {recommendation['name']} ({recommendation['color']}): estimated "
                f"Delta E reduction {recommendation['estimatedDeltaEReduction']:.2f} with "
                f"{recommendation['estimatedMixedSlots']} mixed slots; {recommendation['availability']}."
            )
        if pinned_anchor_keys:
            warnings.append(
                f"{len(pinned_anchor_keys)} Bambu anchor pin(s) were forced. "
                "The planner optimized the remaining physical slots around those choices."
            )
        if mode=="cmykw" and palette_source=="inventory":
            poor=[role for anchor,(role,target) in zip(anchors,CMYK_TARGETS)
                  if dist(anchor_color(anchor),target)>CMYKW_ROLE_WARNING_DE]
            if poor:
                warnings.append("Approximate inventory CMYKW roles: " + ", ".join(poor) +
                                ". Use Exact CMYKW or load closer colors for true roles.")
        real_profiles=[(anchor["preset"],anchor["filamentID"]) for anchor in anchors]
        if plan_only:
            progress(1.0,"Plan preview ready. No 3MF was written.")
            return plan_preview_payload(
                infile,mode,palette_source,planner_mode,planning_sample,
                catalog_region,region_label,catalog_source_label,oldn,real_count,newc,rows,
                anchors,real_profiles,quality_bias,quality_bias_mode,quality,printability,
                recommendation,reference_result,imported,warnings,material_families,pinned_anchor_keys
            )

        representatives=source_slot_representatives(old,anchors,old_slot_to_new_slot,rows,newn)
        progress(0.42,"Remapping painted facets with the Bambu paint-state codec")
        expected_counts=expected_remapped_paint_counts(code_counts,old_slot_to_new_slot,oldn,newn)
        patched=remap_paint_codes_by_codec(tmp, old_slot_to_new_slot, oldn, newn)
        remapped_extruders=remap_model_setting_extruders(tmp,old_slot_to_new_slot)

        progress(0.58,"Preserving source purge transitions and filament properties")
        resize_project_filament_arrays(obj,oldn,representatives,layouts,old,newc)
        obj["filament_colour"]=newc
        obj["filament_settings_id"]=[preset for preset,_ in real_profiles]+[MIXED_PROFILE_ID]*(newn-real_count)
        obj["filament_ids"]=[filament_id for _,filament_id in real_profiles]+[MIXED_FILAMENT_ID]*(newn-real_count)
        obj["filament_is_mixed"]=ism
        obj["filament_mixed_components"]=comps
        obj["filament_mixed_sublayer_ratios"]=ratios
        obj["filament_multi_colour"]=newc[:]
        for key,default in [("filament_colour_type","1"),("default_filament_colour",""),("filament_mixed_gradient","0"),("filament_mixed_gradient_per_part","0"),("filament_mixed_gradient_range",""),("filament_type","PLA"),("filament_vendor","Bambu Lab")]:
            ensure_list(obj,key,newn,default)
        validate_arrays(obj,newn,real_count,layouts,source_off_diagonal_zeros)
        pspath.write_text(json.dumps(obj,indent=2,ensure_ascii=True))

        if staged_outfile.exists(): staged_outfile.unlink()
        progress(0.78,"Writing and reopening the new 3MF archive for validation")
        with zipfile.ZipFile(staged_outfile,"w",zipfile.ZIP_DEFLATED) as z:
            for p in tmp.rglob("*"):
                if p.is_file(): z.write(p,p.relative_to(tmp).as_posix())
        output_codes, output_usage, preserved, color_validation=validate_output_archive(
            staged_outfile,newn,real_count,layouts,source_off_diagonal_zeros,preservation,expected_counts
        )
        if outfile.exists(): outfile.unlink()
        staged_outfile.replace(outfile)

        analysis_assets=None
        if analysis_dir:
            analysis_root=Path(analysis_dir).expanduser().resolve()
            analysis_root.mkdir(parents=True,exist_ok=True)
            heat_colors,influence_colors=analysis_preview_colors(newc,rows,real_count)
            with zipfile.ZipFile(outfile) as written:
                analysis_metrics=project_mesh_metrics(written)
                if analysis_metrics["triangleCount"] > MAX_INTERACTIVE_PREVIEW_TRIANGLES:
                    progress(0.84,"Building optimized preview overlays for large model")
                    heatmap=export_preview_mesh(
                        written,heat_colors,analysis_root/"color-loss.obj","loss",
                        grid_resolution=OPTIMIZED_PREVIEW_GRID_RESOLUTION,
                    )
                    warnings.append(
                        "Using optimized preview overlays for large model; "
                        "full source geometry was reduced only for display."
                    )
                else:
                    progress(0.84,"Building analysis preview overlays")
                    heatmap=export_preview_mesh(written,heat_colors,analysis_root/"color-loss.obj","loss")
            influence=(recolor_preview_mesh(heatmap,influence_colors,analysis_root/"anchor-influence.obj","loss")
                       if heatmap else None)
            predicted=(recolor_preview_mesh(heatmap,newc,analysis_root/"predicted.obj","loss")
                       if heatmap else None)
            analysis_assets={
                "predictedMesh":str(predicted) if predicted else None,
                "heatmapMesh":str(heatmap) if heatmap else None,
                "anchorInfluenceMesh":str(influence) if influence else None,
            }

        with open(csvfile,"w",newline="") as f:
            w=csv.writer(f)
            w.writerow(["old_slot","new_slot","target_color","kind","recipe_label","component_ids","ratios","bambu_reconstructed_color","estimated_deltaE","direct_deltaE","visual_gain"])
            w.writerows(rows)
        color_by_slot={entry["slot"]:entry for entry in color_validation["entries"]}
        color_debug=[]
        for row in rows:
            old_slot,new_slot,target,kind,label,component_ids,ratio_text,preview,error,direct_error,gain=row
            if kind!="MIX":
                continue
            loaded=color_by_slot[new_slot]["bambuLoaded"]
            color_debug.append({
                "oldSlot":old_slot,
                "newSlot":new_slot,
                "target":target,
                "appPrediction":preview,
                "exported":newc[new_slot-1],
                "bambuLoaded":loaded,
                "targetDeltaE":round(dist(target,loaded),2),
                "predictionDeltaE":round(dist(preview,loaded),2),
                "components":component_ids,
                "ratios":ratio_text,
            })
        color_validation["recipes"]=color_debug
        color_report.write_text("\n".join([
            "# Color Validation",
            "",
            f"Output: `{outfile.name}`",
            "",
            "## Result",
            "",
            "- Prediction model: Bambu Studio `FilamentMixer` pigment reconstruction.",
            "- Mixed recipes are reconstructed from physical component slots and the serialized ratio percentages.",
            f"- Maximum app/export versus Bambu reconstructed difference: Delta E {color_validation['maximumDeltaE']:.2f}.",
            "- Validation status: PASS. The archive was reopened after writing and its mixed slot colors were checked.",
            "",
            "## Mixed Color Debug",
            "",
            "| Source | Output | Target | App / Export | Bambu reconstructed | Delta E target | Delta E sync | Recipe |",
            "| ---: | ---: | --- | --- | --- | ---: | ---: | --- |",
            *[
                f"| {entry['oldSlot']} | {entry['newSlot']} | {entry['target']} | "
                f"{entry['appPrediction']} | {entry['bambuLoaded']} | {entry['targetDeltaE']:.2f} | "
                f"{entry['predictionDeltaE']:.2f} | {entry['components']} @ {entry['ratios']} |"
                for entry in color_debug
            ],
            "",
            "## Known Mismatch Causes",
            "",
            "- Older FullSpectrum outputs used a separate perceptual estimate for mixed swatches; Bambu recomputed a different color on load.",
            "- Bambu uses integer percentage weights decoded from the saved four-decimal ratios; evaluating unrounded ratios can select a different swatch.",
            "- A material test print can still differ from the UI because filament translucency, layer height, surface and lighting are physical variables.",
        ]))
        quality_line=(
            f"Quality versus waste priority: Smart auto selected {quality_bias} / 100"
            if quality_bias_mode=="auto"
            else f"Quality versus waste priority: {quality_bias} / 100"
        )
        report.write_text("\n".join([
            "FullSpectrum Studio conversion and validation report",
            f"Mode: {mode}",
            f"Input: {infile.name}",
            f"Output: {outfile.name}",
            *( [f"Imported source: {imported['sourceType']}; {imported['triangleCount']} texture-sampled triangles",
                f"Source clusters / Bambu paint colors: {imported['internalColorCount']} / {imported['exportColorCount']}"]
               if imported else [] ),
            f"Original slots: {oldn}",
            f"Physical filament slots: {real_count}",
            f"Output slots: {newn}",
            f"Original paint codes: {len(ordered_codes)}",
            f"Validated output paint codes: {len(output_codes)}",
            f"Painted output slots: {', '.join(map(str, sorted(output_usage)))}",
            f"Patched model files: {', '.join(patched) if patched else 'none'}",
            f"Remapped object/part extruder assignments: {remapped_extruders}",
            f"Palette source: {palette_source}",
            f"Catalog planning region: {region_label}",
            f"Catalog color source: {catalog_source_label or 'not used for this palette source'}",
            f"Material family filter: {', '.join(material_families) if material_families else 'all supported Bambu PLA families for this source'}",
            f"Manual anchor pins: {', '.join(pinned_anchor_keys) if pinned_anchor_keys else 'none'}",
            f"Planner mode: {planner_mode.title()}",
            f"Planning sample: {'optimized preview mesh weighting' if planning_sample=='preview' else 'original paint-state usage'}",
            quality_line,
            f"Smart search mode: {quality.get('smartSearchMode','manual fixed quality')}",
            f"Skipped smart quality bands: {', '.join(map(str, quality.get('skippedQualityCandidates',[]))) if quality.get('skippedQualityCandidates') else 'none'}",
            "Mixed-color prediction: Bambu Studio FilamentMixer reconstruction",
            f"Mixed-color synchronization after reopen: Delta E {color_validation['maximumDeltaE']:.2f} (verified)",
            f"Inventory source: {'local Bambu Studio inventory selected (quantity details remain in the app only)' if inventory['source'] else 'not used for this palette source'}",
            f"Introduced off-diagonal zero purge transitions: 0",
            f"Estimated mean Delta E: {quality['estimatedDeltaE']:.2f}",
            f"Estimated quality score: {quality['qualityScore']:.1f} / 100",
            f"Confidence score: {quality['confidenceScore']:.1f} / 100 ({quality['confidenceLabel']})",
            f"Brightness error estimate: {quality.get('brightnessError',0):.2f}",
            f"Contrast retention estimate: {quality.get('contrastRetention',0):.1f} / 100",
            f"Painted mixed share: {printability['paintedMixedShare']:.1f}%",
            f"Printability difficulty: {printability['difficulty']} (pre-slice proxy)",
            *( [f"Next-anchor suggestion: {recommendation['name']} {recommendation['color']} "
                f"(estimated Delta E reduction {recommendation['estimatedDeltaEReduction']:.2f}; "
                f"{recommendation['availability']})"] if recommendation else [] ),
            "Time, swap count and actual filament usage: require slicing; not guessed here.",
            f"Geometry and UV preservation: {'verified' if preserved['geometryPreserved'] else 'failed'}",
            f"Texture/resource preservation: {'verified' if preserved['textureResourcesPreserved'] else 'failed'}",
            f"Decoded paint remap equivalence: {'verified' if preserved['paintRemapVerified'] else 'failed'}",
            *( [f"Reference type: {reference_result['kind']}",
                f"Reference similarity estimate: {quality.get('referenceSimilarityScore','not sampled')} / 100"]
               if reference_result else [] ),
            "",
            "Anchors:",
            *[f"{i+1}: {anchor_name(anchor)} {anchor_color(anchor)} [{real_profiles[i][0]} / {real_profiles[i][1]}]"
              + (" owned filament" if anchor["remainingGrams"] is not None else " catalog option")
              for i,anchor in enumerate(anchors)],
            "",
            *(["Warnings:", *warnings, ""] if warnings else []),
            "Validation: OK",
            "Paint mapping decoded and re-encoded from BambuStudio serialized extruder states.",
            "Written 3MF reopened successfully; paint references, mixed slots, Bambu color reconstruction, filament arrays and preserved resources validated."
        ]))

        progress(0.96,f"Validated and saved {outfile.name}")
        if reveal and sys.platform=="darwin":
            subprocess.run(["open","-R",str(outfile)])
        recipes=recipe_items_from_rows(rows,anchors)
        progress(1.0,"Output validated and ready to open in Bambu Studio")
        return {
            "input":str(infile),
            "output":str(outfile),
            "csv":str(csvfile),
            "report":str(report),
            "colorValidationReport":str(color_report),
            "mode":mode,
            "paletteSource":palette_source,
            "plannerMode":planner_mode,
            "planningSample":planning_sample,
            "catalogRegion":catalog_region,
            "catalogRegionLabel":region_label,
            "catalogSource":catalog_source_label,
            "materialFamilies":material_families,
            "pinnedAnchorKeys":pinned_anchor_keys,
            "sourceSlots":oldn,
            "realSlots":real_count,
            "outputSlots":newn,
            "qualityBias":quality_bias,
            "qualityBiasMode":quality_bias_mode,
            "validation":"OK",
            "paintedSlots":sorted(output_usage),
            "quality":quality,
            "colorValidation":color_validation,
            "printability":printability,
            "recommendation":recommendation,
            "preservation":preserved,
            "reference":reference_result,
            "import":imported,
            "analysisAssets":analysis_assets,
            "warnings":warnings,
            "inventory":inventory,
            "anchors":[
                {
                    "key":anchor_key(anchor),
                    "slot":i+1,
                    "name":anchor_name(anchor),
                    "series":str(anchor.get("series") or filament_family(anchor_name(anchor))).strip(),
                    "color":anchor_color(anchor),
                    "preset":real_profiles[i][0],
                    "filamentID":real_profiles[i][1],
                    "remainingGrams":anchor["remainingGrams"],
                }
                for i,anchor in enumerate(anchors)
            ],
            "recipes":recipes,
        }
    finally:
        if staged_outfile.exists():
            staged_outfile.unlink()
        shutil.rmtree(tmp,ignore_errors=True)
        shutil.rmtree(reference_tmp,ignore_errors=True)
        shutil.rmtree(import_tmp,ignore_errors=True)

def main():
    parser=argparse.ArgumentParser(description="FullSpectrum Bambu-compatible 3MF converter")
    parser.add_argument("infile",nargs="?")
    parser.add_argument("--mode",choices=["official","cmykw"])
    parser.add_argument("--palette-source",choices=["inventory","catalog","all-bambu","custom","exact-cmykw"],default="inventory")
    parser.add_argument("--real-slots",choices=["auto","2","3","4","5","6","7","8"],default="auto")
    parser.add_argument("--reference",help="Optional OBJ, GLB or texture image used as a visual reference")
    parser.add_argument("--custom-palette",help="JSON filament library for --palette-source custom")
    parser.add_argument("--quality-bias",default=str(DEFAULT_QUALITY_BIAS),
                        help="Quality versus waste priority from 0-100, or auto for smart planning")
    parser.add_argument("--mix-model",choices=MIX_MODELS,default="bambu",
                        help="Mixed-color model used for planning, export and preview")
    parser.add_argument("--planner-mode",choices=PLANNER_MODES,default="best",
                        help="best uses deeper anchor/mix search; fast keeps the previous quicker planner")
    parser.add_argument("--planning-sample",choices=PLANNING_SAMPLES,default="paint",
                        help="paint uses original paint-state usage; preview weights planning by the optimized viewport mesh")
    parser.add_argument("--plan-preview",action="store_true",
                        help="Run palette planning with the selected options and return JSON without writing a 3MF")
    parser.add_argument("--material-families",
                        help="Comma-separated Bambu PLA families to allow, for example 'PLA Basic,PLA Matte,PLA Pure'")
    parser.add_argument("--anchors",
                        help="Comma-separated Bambu anchor keys to pin, for example 'PLA Basic|#000000,PLA Matte|#FFFFFF'")
    parser.add_argument("--catalog-region",choices=sorted(CATALOG_REGIONS),default="global",
                        help="Planning market shown in catalog warnings and reports")
    parser.add_argument("--analysis-dir",help="Optional local destination for heatmap and anchor-influence preview meshes")
    parser.add_argument("--texture",help="PNG/JPEG texture override used with experimental OBJ import")
    parser.add_argument("--internal-colors",type=int,default=48,
                        help="Experimental OBJ analysis color count before Bambu-compatible compression")
    parser.add_argument("--output-dir")
    parser.add_argument("--json",action="store_true",dest="json_output")
    parser.add_argument("--no-reveal",action="store_true")
    parser.add_argument("--inspect",action="store_true")
    parser.add_argument("--metadata-only",action="store_true",
                        help="Read 3MF palette and thumbnail without mesh metrics or an interactive preview")
    parser.add_argument("--inventory",action="store_true")
    parser.add_argument("--thumbnail-out")
    parser.add_argument("--preview-mesh-out")
    args=parser.parse_args()

    try:
        if args.inventory:
            result=read_bambu_inventory(required=False)
        else:
            infile=Path(args.infile).expanduser() if args.infile else choose_file()
            if not infile or not infile.exists():
                print("No file selected",file=sys.stderr); return 2
            if args.inspect:
                if args.metadata_only and infile.suffix.lower() != ".3mf":
                    raise RuntimeError("Fast metadata-only preview is available for 3MF sources only")
                reporter=(lambda fraction,message: print(json.dumps({"progress":fraction,"message":message}),
                                                           file=sys.stderr,flush=True)) if args.json_output else (lambda fraction,message: None)
                result=inspect_project(infile,args.thumbnail_out,args.preview_mesh_out,args.mix_model,args.texture,reporter,args.metadata_only)
            else:
                if args.mode:
                    mode=args.mode
                elif args.json_output:
                    mode="official"
                else:
                    print("FullSpectrum Studio painted project converter")
                    print("1 = Inventory-optimized Bambu PLA anchors")
                    print("2 = CMYKW roles mapped to stocked PLA")
                    mode="cmykw" if input("Choose mode [1/2]: ").strip()=="2" else "official"
                if args.json_output:
                    reporter=lambda fraction,message: print(json.dumps({"progress":fraction,"message":message}),file=sys.stderr,flush=True)
                else:
                    reporter=lambda fraction,message: print(message,flush=True)
                result=convert(
                    infile,
                    mode,
                    palette_source=args.palette_source,
                    output_dir=args.output_dir,
                    reveal=not args.no_reveal,
                    real_slots=args.real_slots,
                    reference=args.reference,
                    custom_catalog_path=args.custom_palette,
                    quality_bias=args.quality_bias,
                    mix_model=args.mix_model,
                    analysis_dir=args.analysis_dir,
                    texture_override=args.texture,
                    internal_colors=args.internal_colors,
                    catalog_region=args.catalog_region,
                    planner_mode=args.planner_mode,
                    planning_sample=args.planning_sample,
                    plan_only=args.plan_preview,
                    material_families=args.material_families,
                    pinned_anchor_keys=args.anchors,
                    progress=reporter,
                )
        if args.json_output:
            print(json.dumps(result))
        elif args.inspect or args.inventory:
            print(json.dumps(result,indent=2))
        return 0
    except Exception as e:
        message=str(e).strip() or e.__class__.__name__
        print(f"ERROR: {e.__class__.__name__}: {message}",file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return 1

if __name__=="__main__":
    raise SystemExit(main())
