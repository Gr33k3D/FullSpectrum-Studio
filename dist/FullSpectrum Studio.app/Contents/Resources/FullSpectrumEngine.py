#!/usr/bin/env python3
"""
FullSpectrum Studio conversion and validation engine.

Paint is remapped by decoding BambuStudio's serialized TriangleSelector states.
It is never inferred from first-use ordering or a guessed paint code formula.
"""

import argparse
import csv
import hashlib
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
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
# Layer-mixed colors must translate into repeatable cadence patterns. These
# ratios are intentionally small rational schedules rather than arbitrary
# five-percent steps that suggest precision the uncalibrated model cannot offer.
R2 = [(0.25,0.75), (1/3,2/3), (0.5,0.5), (2/3,1/3), (0.75,0.25)]
R3 = [(.6,.2,.2),(.2,.6,.2),(.2,.2,.6),(.5,.3,.2),(.5,.2,.3),(.3,.5,.2),(.2,.5,.3),(.3,.2,.5),(.2,.3,.5),(.4,.4,.2),(.4,.2,.4),(.2,.4,.4),(1/3,1/3,1/3)]

MIN_ANCHOR_DE = 7.0
DIRECT_ANCHOR_DE = 4.5
MIN_MIX_GAIN = 1.0
MAX_RELIABLE_MIX_DE = 8.0
CMYKW_ROLE_WARNING_DE = 10.0
MAX_BAMBU_PAINT_SLOT = 32
PREVIEW_GRID_RESOLUTION = 72
MIN_REAL_SLOTS = 2
MAX_REAL_SLOTS = 6
MAX_ARCHIVE_ENTRIES = 20000
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 2 * 1024 * 1024 * 1024
MAX_REFERENCE_BYTES = 600 * 1024 * 1024
MAX_IMPORT_FACES = 2_000_000
MAX_INTERACTIVE_PREVIEW_TRIANGLES = 750_000
OPTIMIZED_PREVIEW_GRID_RESOLUTION = 72
OUTPUT_VERSION = "v0.4.3"
DEFAULT_QUALITY_BIAS = 60
MIX_MODELS = ("bambu",)
HEX_DIGITS = "0123456789ABCDEF"
PAINT_PATTERN = re.compile(r'paint_color="([^"]+)"')
PAINT_BYTES_PATTERN = re.compile(br'paint_color="[^"]+"')
XML_ATTRIBUTE_PATTERN = re.compile(r'([A-Za-z_:][\w:.-]*)="([^"]*)"')
PROFILE_BY_FAMILY = {
    "PLA Basic": ("Bambu PLA Basic @BBL H2C 0.2 nozzle", "GFA00"),
    "PLA Matte": ("Bambu PLA Matte @BBL H2C 0.2 nozzle", "GFA01"),
    "PLA Silk+": ("Bambu PLA Silk+ @BBL H2C 0.2 nozzle", "GFA06"),
}
MIXED_PROFILE_ID, MIXED_FILAMENT_ID = PROFILE_BY_FAMILY["PLA Basic"]
BAMBU_INVENTORY_LOCATIONS = [
    ("Bambu Studio Beta", Path.home()/"Library"/"Application Support"/"BambuStudioBeta"/"filament_inventory"/"spools.json"),
    ("Bambu Studio", Path.home()/"Library"/"Application Support"/"BambuStudio"/"filament_inventory"/"spools.json"),
]
if os.name == "nt" and os.environ.get("APPDATA"):
    BAMBU_INVENTORY_LOCATIONS = [
        ("Bambu Studio Beta", Path(os.environ["APPDATA"])/"BambuStudioBeta"/"filament_inventory"/"spools.json"),
        ("Bambu Studio", Path(os.environ["APPDATA"])/"BambuStudio"/"filament_inventory"/"spools.json"),
    ]

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
def dist(a,b):
    return delta_e_2000(rgb_to_lab(*rgb(a)), rgb_to_lab(*rgb(b)))
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

@lru_cache(maxsize=8192)
def cached_bambu_mix(hexes, weights):
    return bambu_blend_color_multi(hexes,weights)

def mix(hexes, ratios, model="bambu"):
    """Return the exact swatch Bambu Studio reconstructs for a mixed recipe."""
    weights=tuple(bambu_ratio_weights(ratios))
    return cached_bambu_mix(tuple(hx(color) for color in hexes),weights)

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
    obj,_=json.JSONDecoder().raw_decode(path.read_text(errors="replace").lstrip())
    return obj

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
        digest.update(PAINT_BYTES_PATTERN.sub(b'paint_color=""',block) if normalize_paint else block)
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
    out=[]
    v=obj.get("filament_colour",[])
    if isinstance(v,list):
        for x in v:
            if re.match(r"#?[0-9A-Fa-f]{6}$", str(x).strip()):
                out.append(hx(x).upper())
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
    for family, values in PROFILE_BY_FAMILY.items():
        if name.startswith(family):
            return values
    return PROFILE_BY_FAMILY["PLA Basic"]

def filament_family(name):
    return next((family for family in PROFILE_BY_FAMILY if name == family or name.startswith(f"{family} ")), "PLA Basic")

@lru_cache(maxsize=1)
def installed_bambu_color_names():
    roots=[
        Path.home()/"Library"/"Application Support"/"BambuStudioBeta",
        Path.home()/"Library"/"Application Support"/"BambuStudio",
    ]
    if os.name == "nt" and os.environ.get("APPDATA"):
        roots=[
            Path(os.environ["APPDATA"])/"BambuStudioBeta",
            Path(os.environ["APPDATA"])/"BambuStudio",
        ]
    names={}
    for root in roots:
        catalog=root/"system"/"BBL"/"filament"/"filaments_color_codes.json"
        if not catalog.exists():
            continue
        try:
            rows=json.loads(catalog.read_text(errors="replace")).get("data",[])
        except (OSError, ValueError, AttributeError):
            continue
        for row in rows:
            if not isinstance(row,dict):
                continue
            series=str(row.get("fila_type") or "").strip()
            english=(row.get("fila_color_name") or {}).get("en")
            if not series or not english:
                continue
            for color in row.get("fila_color") or []:
                names.setdefault((series,hx(color)),f"{series} {english}")
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
    inventory_match=next(((label,path) for label,path in BAMBU_INVENTORY_LOCATIONS if path.exists()),None)
    inventory_label,inventory_path=inventory_match if inventory_match else (None,None)
    if inventory_path is None:
        if required:
            raise RuntimeError("Bambu Studio filament inventory was not found. Enable Inventory Beta and add active PLA spools.")
        return {"source":None,"allCount":0,"usableCount":0,"totalGrams":0.0,"spools":[]}
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

def catalog_palette(scope="core", inventory=None):
    options=[]
    for name,color in BAMBU_PLA:
        preset,filament_id=profile_for_anchor(name)
        options.append({
            "name":name,
            "series":filament_family(name),
            "brand":"Bambu Lab",
            "color":hx(color),
            "preset":preset,
            "filamentID":filament_id,
            "remainingGrams":None,
            "initialGrams":None,
            "availability":"confirm-regionally",
        })
    if scope=="all" and inventory:
        existing={(item["series"],item["color"]) for item in options}
        for spool in inventory.get("spools",[]):
            key=(spool["series"],spool["color"])
            if key not in existing and spool.get("brand","").lower().startswith("bambu"):
                option=dict(spool)
                option["availability"]="local-inventory"
                options.append(option)
                existing.add(key)
    return options

def custom_palette(path):
    if not path:
        raise RuntimeError("Custom brands source requires a palette JSON file.")
    payload=json.loads(Path(path).expanduser().read_text(errors="replace"))
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
            pixels=list(source.convert("RGB").resize((96,96)).getdata())
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
                    if code not in ordered:
                        ordered.append(code)
    return ordered, counts

def collect_archive_paint_codes(archive):
    ordered=[]
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
                    if code not in ordered:
                        ordered.append(code)
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
                attrs=dict(XML_ATTRIBUTE_PATTERN.findall(raw_line.decode("utf-8", errors="replace")))
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
                attrs=dict(XML_ATTRIBUTE_PATTERN.findall(raw_line.decode("utf-8", errors="replace")))
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

def nearest_anchor_error(color, anchors):
    return min((dist(color,anchor_color(anchor)),i+1,anchor_name(anchor),anchor_color(anchor))
               for i,anchor in enumerate(anchors))

def best_mix_recipe(color, anchors, mix_model="bambu", allow_three=True):
    ah=[anchor_color(anchor) for anchor in anchors]
    best_err=999999.0; best=None
    for i,j in combinations(range(len(anchors)),2):
        for r0,r1 in R2:
            p=mix([ah[i],ah[j]],[r0,r1],mix_model); d=dist(color,p)
            if d<best_err:
                best_err=d; best=([i+1,j+1],[r0,r1],p)
    if best is None:
        direct=nearest_anchor_error(color,anchors)
        return [direct[1]],[1.0],direct[3],direct[0]
    if allow_three and best_err>12:
        best3_err=best_err; best3=best
        for combo in combinations(range(len(anchors)),3):
            for r0,r1,r2 in R3:
                p=mix([ah[combo[0]],ah[combo[1]],ah[combo[2]]],[r0,r1,r2],mix_model); d=dist(color,p)
                if d<best3_err:
                    best3_err=d; best3=([combo[0]+1,combo[1]+1,combo[2]+1],[r0,r1,r2],p)
        if (best_err-best3_err)>=2.5 and ((best_err-best3_err)/max(best_err,1e-9))>=0.15:
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

def select_anchors(old_colors, usage, mode, inventory, palette_source, real_slots="auto",
                   custom_catalog_path=None, reference=None, mix_model="bambu",
                   quality_bias=DEFAULT_QUALITY_BIAS):
    requested=None if str(real_slots)=="auto" else int(real_slots)
    minimum=4 if mode=="cmykw" else MIN_REAL_SLOTS
    if requested is not None and (requested<minimum or requested>MAX_REAL_SLOTS):
        raise RuntimeError(f"{mode.upper()} strategy requires {minimum}-{MAX_REAL_SLOTS} physical slots")
    if palette_source=="exact-cmykw":
        if mode!="cmykw":
            raise RuntimeError("Exact CMYKW filament source requires the CMYKW palette strategy")
        return exact_cmykw_palette()[:requested or MAX_REAL_SLOTS]
    if palette_source=="inventory":
        pool=inventory_palette(inventory)
    elif palette_source=="custom":
        pool=custom_palette(custom_catalog_path)
    else:
        pool=catalog_palette("all" if palette_source=="all-bambu" else "core",inventory)
    used=[(i+1,c,float(usage.get(i+1,0))) for i,c in enumerate(old_colors) if usage.get(i+1,0)>0]
    if not used: used=[(i+1,c,1.0) for i,c in enumerate(old_colors)]
    total=sum(w for _,_,w in used) or 1.0
    targets=list(used)
    if reference and reference.get("dominantColors"):
        # A source texture can expose important colors which sparse painted
        # facet usage understates. Keep it influential, never dominant.
        reference_weight=total*(0.10+0.001*max(0,min(100,quality_bias)))
        targets.extend((0,item["color"],reference_weight*item["weight"])
                       for item in reference["dominantColors"])
    target_total=sum(w for _,_,w in targets) or 1.0
    def score(anchors):
        ah=[anchor_color(anchor) for anchor in anchors]
        s=0.0
        for _,c,w in targets:
            direct=min(dist(c,a) for a in ah)
            pair=direct
            for i,j in combinations(range(len(ah)),2):
                candidate=dist(c,mix([ah[i],ah[j]],[.5,.5],mix_model))
                if candidate<=MAX_RELIABLE_MIX_DE:
                    pair=min(pair,candidate)
            s+=(w/target_total)*pair
        lums=[luminance(a) for a in ah]
        if max(lums)<210: s+=12
        if min(lums)>65: s+=12
        for i in range(len(ah)):
            for j in range(i+1,len(ah)):
                d=dist(ah[i],ah[j])
                if d<MIN_ANCHOR_DE: s+=(MIN_ANCHOR_DE-d)*4
        return s
    def choose_count(count):
        if len({anchor_color(item) for item in pool})<count:
            raise RuntimeError(f"Filament source contains fewer than {count} distinct colors")
        if mode=="cmykw":
            return select_cmykw_anchors(pool,count)
        selected=[]
        if any(luminance(c)>205 and (w/total)>.01 for _,c,w in used):
            selected.append(min(pool,key=lambda b:abs(luminance(anchor_color(b))-245)))
        if len(selected)<count and any(luminance(c)<75 and (w/total)>.01 for _,c,w in used):
            dark=min(pool,key=lambda b:luminance(anchor_color(b)))
            if dark not in selected: selected.append(dark)
        while len(selected)<count:
            best=None
            for cand in pool:
                if cand in selected: continue
                if any(dist(anchor_color(cand),anchor_color(item))<MIN_ANCHOR_DE for item in selected): continue
                candidate=(score(selected+[cand]),cand)
                if best is None or candidate[0]<best[0]: best=candidate
            if best is None:
                best=next(((0,cand) for cand in pool if cand not in selected),None)
            if best is None:
                raise RuntimeError("Could not find enough distinct physical filament anchors")
            selected.append(best[1])
        current=selected[:count]; current_score=score(current)
        improved=True
        while improved:
            improved=False
            for index in range(count):
                for candidate in pool:
                    if candidate in current: continue
                    trial=current[:]; trial[index]=candidate
                    if any(dist(anchor_color(a),anchor_color(b))<MIN_ANCHOR_DE
                           for ix,a in enumerate(trial) for b in trial[ix+1:]):
                        continue
                    candidate_score=score(trial)
                    if candidate_score+1e-6<current_score:
                        current=trial; current_score=candidate_score; improved=True; break
                if improved: break
        return current
    counts=[requested] if requested is not None else list(range(minimum,MAX_REAL_SLOTS+1))
    trials=[]
    for count in counts:
        anchors=choose_count(count)
        weighted=0.0
        for _,color,weight in used:
            direct=nearest_anchor_error(color,anchors)[0]
            mix_error=best_mix_recipe(color,anchors,mix_model,quality_bias>=70)[3]
            printable_error=mix_error if mix_error<=MAX_RELIABLE_MIX_DE else direct
            weighted+=(weight/total)*min(direct,printable_error)
        # A new physical slot must buy noticeable visual improvement.
        physical_penalty=(count-minimum)*(1.35-(max(0,min(100,quality_bias))/100)*0.9)
        trials.append((weighted+physical_penalty,weighted,anchors))
    return min(trials,key=lambda trial:trial[0])[2]

def build_palette(old_colors, anchors, usage=None, quality_bias=DEFAULT_QUALITY_BIAS, mix_model="bambu"):
    real_count=len(anchors)
    newc=[anchor_color(anchor) for anchor in anchors]
    ism=["0"]*real_count; comps=[""]*real_count; ratios=[""]*real_count
    old_slot_to_new_slot={}
    rows_by_slot={}
    next_slot=real_count+1
    quality_bias=max(0,min(100,int(quality_bias)))
    min_gain=MIN_MIX_GAIN+(100-quality_bias)*0.045
    max_unique_mixes=max(2,min(MAX_BAMBU_PAINT_SLOT-real_count,3+round(quality_bias/6)))
    mix_candidates=[]
    for old_slot,target in enumerate(old_colors, start=1):
        direct_err,direct_slot,direct_name,direct_hex=nearest_anchor_error(target,anchors)
        cs,rs,preview,mix_err=best_mix_recipe(target,anchors,mix_model,quality_bias>=70)
        gain=direct_err-mix_err
        weight=float((usage or {}).get(old_slot,1.0))
        old_slot_to_new_slot[old_slot]=direct_slot
        rows_by_slot[old_slot]=[old_slot,direct_slot,target,"ANCHOR",direct_name,"","",
                                direct_hex,f"{direct_err:.2f}",f"{direct_err:.2f}","0.00"]
        if direct_err>DIRECT_ANCHOR_DE and gain>=min_gain and mix_err<=MAX_RELIABLE_MIX_DE:
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
    result={
        "estimatedDeltaE":round(estimated,2),
        "maximumDeltaE":round(maximum,2),
        "qualityScore":round(max(0.0,100.0-estimated*2.2),1),
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
        suggestions.append("Move the quality-versus-waste control toward practical to reduce logical mixed colors.")
    if mixed_share>0.55:
        suggestions.append("Most painted usage is mixed; run a small calibration print before committing material.")
    if real_count<MAX_REAL_SLOTS and len(used_mixed_slots)>4:
        suggestions.append("An additional owned physical anchor may reduce mixed regions and purge risk.")
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

def candidate_palette(palette_source, inventory, custom_catalog_path):
    if palette_source=="inventory":
        return inventory_palette(inventory)
    if palette_source=="custom":
        return custom_palette(custom_catalog_path)
    if palette_source=="exact-cmykw":
        return []
    return catalog_palette("all" if palette_source=="all-bambu" else "core",inventory)

def additional_anchor_recommendation(old_colors, usage, anchors, palette_source, inventory,
                                     custom_catalog_path, quality_bias, mix_model, current_quality):
    if len(anchors)>=MAX_REAL_SLOTS or palette_source=="exact-cmykw":
        return None
    selected={anchor_color(anchor) for anchor in anchors}
    best=None
    for candidate in candidate_palette(palette_source,inventory,custom_catalog_path):
        if anchor_color(candidate) in selected:
            continue
        trial=anchors+[candidate]
        newc,_,_,_,_,rows=build_palette(old_colors,trial,usage,quality_bias,mix_model)
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
        "name":anchor_name(candidate),
        "color":anchor_color(candidate),
        "estimatedDeltaEReduction":round(gain,2),
        "estimatedQualityScore":metrics["qualityScore"],
        "estimatedMixedSlots":mix_count,
        "availability":"owned" if palette_source=="inventory" else "confirm before purchase",
    }

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
            with p.open("r",errors="replace") as source, replacement.open("w") as output:
                for text in source:
                    def repl(m):
                        nonlocal changed
                        code=m.group(1).upper()
                        if code not in cache:
                            cache[code], _=remap_paint_code(code, old_slot_to_new_slot, oldn, newn)
                        mapped=f'paint_color="{cache[code]}"'
                        changed=changed or mapped != m.group(0)
                        return mapped
                    output.write(PAINT_PATTERN.sub(repl,text))
            if changed:
                replacement.replace(p)
                patched.append(str(p.relative_to(tmp)))
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
                    if slot < 1 or slot > newn:
                        raise RuntimeError(f"Object metadata references missing extruder slot {slot}")
        preservation_result=verify_preservation(archive,preservation) if preservation else None
        if preservation_result is not None:
            preservation_result["paintRemapVerified"]=expected_paint_counts is not None
    return paint_codes, usage, preservation_result, color_validation

def convert(infile, mode, palette_source="inventory", output_dir=None, reveal=True, real_slots="auto",
            reference=None, custom_catalog_path=None, quality_bias=DEFAULT_QUALITY_BIAS,
            mix_model="bambu", analysis_dir=None, texture_override=None,
            internal_colors=48, progress=lambda fraction,message: None):
    infile=Path(infile).expanduser().resolve()
    quality_bias=max(0,min(100,int(quality_bias)))
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
            progress(0.12,f"Using {len(catalog_palette('all' if palette_source=='all-bambu' else 'core',inventory))} Bambu Lab planning colors")
            warnings.append("Catalog colors are planning choices; confirm current regional availability before buying filament.")
        with zipfile.ZipFile(project_file) as z:
            names=z.namelist()
            safe_extract_archive(z,tmp)
        psrel=find_project_settings(names)
        if not psrel: raise RuntimeError("No project_settings.config found")
        pspath=tmp/psrel
        obj=read_json_config(pspath)
        old=colors_from_project(obj); oldn=len(old)
        if not old: raise RuntimeError("No filament_colour array found")
        preservation=preservation_snapshot(tmp,psrel)
        reference_result=analyze_reference(reference,reference_tmp) if reference else None
        ordered_codes, code_counts=collect_paint_codes(tmp)
        usage=paint_slot_usage(code_counts, oldn)
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
        progress(0.22,"Generating anchors from painted colors and " + source_label)
        anchors=select_anchors(old, usage, mode, inventory, palette_source,real_slots,
                               custom_catalog_path,reference_result,mix_model,quality_bias)
        real_count=len(anchors)
        progress(0.34,"Building mixes with useful predicted visual gain")
        newc,ism,comps,ratios,old_slot_to_new_slot,rows=build_palette(
            old,anchors,usage,quality_bias,mix_model
        )
        newn=len(newc)
        if newn > MAX_BAMBU_PAINT_SLOT:
            raise RuntimeError(f"Output requires {newn} slots, but Bambu paint_color supports only {MAX_BAMBU_PAINT_SLOT}")

        representatives=source_slot_representatives(old,anchors,old_slot_to_new_slot,rows,newn)
        progress(0.42,"Remapping painted facets with the Bambu paint-state codec")
        expected_counts=expected_remapped_paint_counts(code_counts,old_slot_to_new_slot,oldn,newn)
        patched=remap_paint_codes_by_codec(tmp, old_slot_to_new_slot, oldn, newn)
        remapped_extruders=remap_model_setting_extruders(tmp,old_slot_to_new_slot)

        progress(0.58,"Preserving source purge transitions and filament properties")
        resize_project_filament_arrays(obj,oldn,representatives,layouts,old,newc)
        obj["filament_colour"]=newc
        real_profiles=[(anchor["preset"],anchor["filamentID"]) for anchor in anchors]
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
        quality=quality_metrics(rows,usage,old,reference_result,mix_model)
        printability=printability_metrics(rows,usage,real_count,newn,layouts,obj)
        unmatched=[
            row for row in rows
            if usage.get(row[0],0)>0 and float(row[8])>MAX_RELIABLE_MIX_DE
        ]
        if unmatched:
            warnings.append(
                f"{len(unmatched)} painted colors have no reliable match within Delta E "
                f"{MAX_RELIABLE_MIX_DE:.0f}; nearest physical colors were kept instead "
                "of creating misleading mixed recipes. Add closer filament colors for these regions."
            )
        recommendation=additional_anchor_recommendation(
            old,usage,anchors,palette_source,inventory,custom_catalog_path,
            quality_bias,mix_model,quality
        )
        if recommendation:
            printability["recommendations"].append(
                f"Consider {recommendation['name']} ({recommendation['color']}): estimated "
                f"Delta E reduction {recommendation['estimatedDeltaEReduction']:.2f} with "
                f"{recommendation['estimatedMixedSlots']} mixed slots; {recommendation['availability']}."
            )
        if mode=="cmykw" and palette_source=="inventory":
            poor=[role for anchor,(role,target) in zip(anchors,CMYK_TARGETS)
                  if dist(anchor_color(anchor),target)>CMYKW_ROLE_WARNING_DE]
            if poor:
                warnings.append("Approximate inventory CMYKW roles: " + ", ".join(poor) +
                                ". Use Exact CMYKW or load closer colors for true roles.")

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
            f"Quality versus waste priority: {quality_bias} / 100",
            "Mixed-color prediction: Bambu Studio FilamentMixer reconstruction",
            f"Mixed-color synchronization after reopen: Delta E {color_validation['maximumDeltaE']:.2f} (verified)",
            f"Inventory source: {'local Bambu Studio Beta inventory (read only)' if inventory['source'] else 'not used for this palette source'}",
            f"Available PLA inventory: {inventory['usableCount']} spools / {inventory['totalGrams']:.0f} g",
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
              + (f" {anchor['remainingGrams']:.0f} g available" if anchor["remainingGrams"] is not None else " catalog option")
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
        recipes=[]
        for old_slot,new_slot,target,kind,label,component_ids,ratio_text,preview,error,direct_error,gain in rows:
            available_grams=None
            if kind=="MIX" and all(anchors[int(value)-1]["remainingGrams"] is not None for value in component_ids.split(",")):
                component_slots=[int(value) for value in component_ids.split(",")]
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
        progress(1.0,"Output validated and ready to open in Bambu Studio")
        return {
            "input":str(infile),
            "output":str(outfile),
            "csv":str(csvfile),
            "report":str(report),
            "colorValidationReport":str(color_report),
            "mode":mode,
            "paletteSource":palette_source,
            "sourceSlots":oldn,
            "realSlots":real_count,
            "outputSlots":newn,
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
                    "slot":i+1,
                    "name":anchor_name(anchor),
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
    parser.add_argument("--real-slots",choices=["auto","2","3","4","5","6"],default="auto")
    parser.add_argument("--reference",help="Optional OBJ, GLB or texture image used as a visual reference")
    parser.add_argument("--custom-palette",help="JSON filament library for --palette-source custom")
    parser.add_argument("--quality-bias",type=int,default=DEFAULT_QUALITY_BIAS,
                        help="Quality versus waste priority from 0 (fewer mixes) to 100 (more detail)")
    parser.add_argument("--mix-model",choices=MIX_MODELS,default="bambu",
                        help="Mixed-color model used for planning, export and preview")
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
            result=read_bambu_inventory()
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
                    progress=reporter,
                )
        if args.json_output:
            print(json.dumps(result))
        elif args.inspect or args.inventory:
            print(json.dumps(result,indent=2))
        return 0
    except Exception as e:
        print("ERROR:",e,file=sys.stderr)
        if os.environ.get("FULLSPECTRUM_DEBUG") == "1":
            import traceback
            traceback.print_exc(file=sys.stderr)
        return 1

if __name__=="__main__":
    raise SystemExit(main())
