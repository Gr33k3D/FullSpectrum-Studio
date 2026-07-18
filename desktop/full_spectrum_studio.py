#!/usr/bin/env python3
"""Cross-platform FullSpectrum Studio desktop shell for the shared engine."""

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import tkinter as tk
from datetime import datetime, timezone
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

MODULE_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
if str(MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(MODULE_ROOT))

from desktop.app_support import (
    APP_ROOT,
    APP_VERSION,
    format_plan_preview,
    format_shareable_error_report,
    plan_forecast,
    privacy_safe_error_message,
)


def load_engine():
    engine_path = APP_ROOT / "fullspectrum_engine.py"
    root_path = str(APP_ROOT)
    if root_path not in sys.path:
        sys.path.insert(0, root_path)
    spec = importlib.util.spec_from_file_location("fullspectrum_engine", engine_path)
    engine = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(engine)
    return engine


ENGINE = load_engine()


class StudioApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"FullSpectrum Studio {APP_VERSION}")
        self.geometry("1220x820")
        self.minsize(980, 660)
        self.configure(bg="#151719")
        self.project = tk.StringVar()
        self.reference = tk.StringVar()
        self.texture = tk.StringVar()
        self.custom = tk.StringVar()
        self.strategy = tk.StringVar(value="official")
        self.planner_mode = tk.StringVar(value="best")
        self.planning_sample = tk.StringVar(value="preview")
        self.source = tk.StringVar(value="inventory")
        self.catalog_region = tk.StringVar(value="global")
        self.real_slots = tk.StringVar(value="auto")
        self.mix_model = tk.StringVar(value="bambu")
        self.quality_bias = tk.IntVar(value=60)
        self.smart_quality = tk.BooleanVar(value=True)
        self.auto_preview = tk.BooleanVar(value=True)
        self.auto_open = tk.BooleanVar(value=True)
        self.output_application = tk.StringVar(value="Bambu Studio")
        self.progress = tk.DoubleVar(value=0)
        self.status = tk.StringVar(value="Choose a painted .3mf or textured OBJ / GLB source to begin.")
        self.cancel_requested = False
        self.worker_active = False
        self.last_progress_time = time.monotonic()
        self.last_engine_message = "Waiting for a model."
        self.last_error_report = ""
        self.last_error_log = None
        self.operation_name = "Operation"
        self.settings_revision = 0
        self.auto_preview_dirty = False
        self.auto_preview_after = None
        self.source_preview_photo = None
        self.last_plan_result = None
        self.inventory_snapshot = None
        self.disabled_anchor_keys = set()
        self.pinned_anchor_keys = set()
        self.filament_selection_summary = tk.StringVar(value="Loading filament colors...")
        self._build()
        threading.Thread(target=self._refresh_inventory, daemon=True).start()

    def _build(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", background="#151719", foreground="#eef2f3", fieldbackground="#24282b")
        style.configure("TButton", padding=8, foreground="#f6f8f8", background="#292e32")
        style.map("TButton", foreground=[("active", "#ffffff"), ("pressed", "#ffffff"), ("disabled", "#7f898f")], background=[("active", "#343b40"), ("pressed", "#202427")])
        style.configure("Accent.TButton", padding=9, foreground="#081113", background="#55bdcf", font=("Segoe UI", 10, "bold"))
        style.map("Accent.TButton", background=[("active", "#73ccda"), ("pressed", "#42aabc"), ("disabled", "#41575c")])
        style.configure("TCombobox", foreground="#f6f8f8", fieldbackground="#24282b", background="#292e32", arrowcolor="#f6f8f8")
        style.map("TCombobox", foreground=[("readonly", "#f6f8f8")], fieldbackground=[("readonly", "#24282b")], selectforeground=[("readonly", "#f6f8f8")], selectbackground=[("readonly", "#24282b")])
        style.configure("Title.TLabel", font=("Segoe UI", 20, "bold"), foreground="#f7f9f9")
        style.configure("Section.TLabel", font=("Segoe UI", 9, "bold"), foreground="#75c6d4")
        style.configure("Metric.TLabel", font=("Segoe UI", 11, "bold"), foreground="#f1f5f5")
        style.configure("Small.TLabel", foreground="#98a5ab")
        style.configure("Warning.TLabel", foreground="#eba85e")
        self.configure(bg="#151719")

        shell = ttk.Frame(self, padding=(18, 14, 18, 18))
        shell.pack(fill="both", expand=True)
        title_row = ttk.Frame(shell)
        title_row.pack(fill="x", pady=(0, 12))
        ttk.Label(title_row, text="FullSpectrum Studio", style="Title.TLabel").pack(side="left")
        ttk.Label(title_row, text="Automatic palette forecast", style="Small.TLabel").pack(side="left", padx=(14, 0), pady=(6, 0))
        ttk.Label(title_row, text=f"v{APP_VERSION}", style="Small.TLabel").pack(side="right", pady=(6, 0))

        workspace = ttk.Panedwindow(shell, orient="horizontal")
        workspace.pack(fill="both", expand=True)
        left_shell = ttk.Frame(workspace, width=445)
        right = ttk.Frame(workspace, padding=(18, 0, 0, 0))
        workspace.add(left_shell, weight=0)
        workspace.add(right, weight=1)

        canvas = tk.Canvas(left_shell, bg="#151719", highlightthickness=0, borderwidth=0, width=430)
        scrollbar = ttk.Scrollbar(left_shell, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        frame = ttk.Frame(canvas, padding=(2, 2, 14, 18))
        content_window = canvas.create_window((0, 0), window=frame, anchor="nw")
        frame.bind("<Configure>", lambda _: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(content_window, width=event.width))
        self.content_canvas = canvas

        ttk.Label(frame, text="SOURCE", style="Section.TLabel").pack(anchor="w", pady=(0, 7))

        for title, variable, action in [
            ("Painted 3MF or textured model", self.project, self.choose_project),
            ("OBJ texture", self.texture, self.choose_texture),
            ("Visual reference", self.reference, self.choose_reference),
            ("Custom filament library", self.custom, self.choose_custom),
        ]:
            ttk.Label(frame, text=title, style="Small.TLabel").pack(anchor="w", pady=(7, 3))
            row = ttk.Frame(frame)
            row.pack(fill="x")
            ttk.Entry(row, textvariable=variable).pack(side="left", fill="x", expand=True)
            ttk.Button(row, text="Browse", command=action).pack(side="left", padx=(8, 0))

        ttk.Separator(frame).pack(fill="x", pady=18)
        ttk.Label(frame, text="PLAN", style="Section.TLabel").pack(anchor="w", pady=(0, 8))
        choices = ttk.Frame(frame)
        choices.pack(fill="x")
        self.combo(choices, "Strategy", self.strategy, ["official", "cmykw"], 0, 0)
        self.combo(choices, "Planner", self.planner_mode, ["best", "fast"], 1, 0)
        self.combo(choices, "Filaments", self.source, ["inventory", "catalog", "all-bambu", "custom", "exact-cmykw"], 2, 0)
        self.combo(choices, "Physical slots", self.real_slots, ["auto", "2", "3", "4", "5", "6", "7", "8"], 0, 1)
        self.combo(choices, "Catalog region", self.catalog_region, ["global", "eu", "us-ca", "uk", "au-nz", "asia"], 1, 1)
        self.combo(choices, "Planning sample", self.planning_sample, ["paint", "preview"], 2, 1)

        filament_row = ttk.Frame(frame)
        filament_row.pack(fill="x", pady=(2, 10))
        self.filament_button = ttk.Button(
            filament_row, text="Choose Filament Colors", command=self.open_filament_selector
        )
        self.filament_button.pack(side="left")
        ttk.Label(
            filament_row, textvariable=self.filament_selection_summary, style="Small.TLabel"
        ).pack(side="left", padx=(10, 0), fill="x", expand=True)

        handoff = ttk.Frame(frame)
        handoff.pack(fill="x", pady=(8, 12))
        ttk.Checkbutton(handoff, text="Open validated output in", variable=self.auto_open).pack(side="left")
        ttk.Combobox(
            handoff, textvariable=self.output_application,
            values=["Bambu Studio", "OrcaSlicer"], state="readonly", width=18
        ).pack(side="left", padx=(8, 0))

        slider = ttk.Frame(frame)
        slider.pack(fill="x", pady=(0, 14))
        ttk.Checkbutton(slider, text="Smart quality", variable=self.smart_quality).pack(side="left")
        tk.Scale(
            slider, from_=0, to=100, orient="horizontal", variable=self.quality_bias,
            bg="#151719", fg="#d9e1e3", highlightthickness=0, troughcolor="#24282b",
            activebackground="#55bdcf", length=220
        ).pack(side="left", fill="x", expand=True, padx=(12, 0))

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(4, 10))
        self.preview_button = ttk.Button(buttons, text="Preview Plan", command=self.preview_plan)
        self.preview_button.pack(side="left")
        self.convert_button = ttk.Button(buttons, text="Compose Palette", command=self.convert, style="Accent.TButton")
        self.convert_button.pack(side="left", padx=(8, 0))
        self.cancel_button = ttk.Button(buttons, text="Cancel", command=self.cancel_conversion, state="disabled")
        self.cancel_button.pack(side="left", padx=8)

        tools = ttk.Frame(frame)
        tools.pack(fill="x")
        self.folder_button = ttk.Button(tools, text="Show Output", command=self.open_folder, state="disabled")
        self.folder_button.pack(side="left")
        self.copy_error_button = ttk.Button(tools, text="Copy Error Report", command=self.copy_error_report, state="disabled")
        self.copy_error_button.pack(side="left", padx=(8, 0))

        forecast_header = ttk.Frame(right)
        forecast_header.pack(fill="x", pady=(0, 9))
        ttk.Label(forecast_header, text="LIVE FORECAST", style="Section.TLabel").pack(side="left")
        ttk.Checkbutton(forecast_header, text="Automatic", variable=self.auto_preview).pack(side="right")

        self.preview_canvas = tk.Canvas(right, height=300, bg="#0f1112", highlightthickness=1, highlightbackground="#30363a")
        self.preview_canvas.pack(fill="x")
        self.preview_canvas.create_text(260, 150, text="Open a model to preview", fill="#768187", font=("Segoe UI", 13))

        forecast_row = ttk.Frame(right, padding=(0, 14, 0, 8))
        forecast_row.pack(fill="x")
        self.accuracy_canvas = tk.Canvas(forecast_row, width=112, height=112, bg="#151719", highlightthickness=0)
        self.accuracy_canvas.pack(side="left")
        self.accuracy_value = tk.StringVar(value="--%")
        self.confidence_value = tk.StringVar(value="--%")
        self.error_value = tk.StringVar(value="dE --")
        self.slots_value = tk.StringVar(value="No plan")
        metrics = ttk.Frame(forecast_row)
        metrics.pack(side="left", fill="both", expand=True, padx=(18, 0))
        for title, variable in [
            ("Estimated accuracy", self.accuracy_value),
            ("Confidence", self.confidence_value),
            ("Worst match", self.error_value),
            ("Palette", self.slots_value),
        ]:
            row = ttk.Frame(metrics)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=title, style="Small.TLabel").pack(side="left")
            ttk.Label(row, textvariable=variable, style="Metric.TLabel").pack(side="right")
        self._draw_accuracy(0, empty=True)

        ttk.Label(right, text="EXPECTED PALETTE", style="Section.TLabel").pack(anchor="w", pady=(7, 6))
        self.palette_canvas = tk.Canvas(right, height=44, bg="#151719", highlightthickness=0)
        self.palette_canvas.pack(fill="x")
        self.gap_message = tk.StringVar(value="")
        gap_row = ttk.Frame(right)
        gap_row.pack(fill="x", pady=(5, 8))
        self.gap_label = ttk.Label(gap_row, textvariable=self.gap_message, style="Warning.TLabel", wraplength=520, justify="left")
        self.gap_label.pack(side="left", fill="x", expand=True)
        self.suggestion_button = ttk.Button(gap_row, text="Use suggestion", command=self.use_forecast_suggestion, state="disabled")
        self.suggestion_button.pack(side="right", padx=(10, 0))

        ttk.Progressbar(right, variable=self.progress, maximum=100).pack(fill="x", pady=(2, 7))
        ttk.Label(right, textvariable=self.status, style="Small.TLabel", wraplength=680, justify="left").pack(anchor="w")
        self.output = tk.Text(right, height=11, bg="#1c2023", fg="#dce4e6", insertbackground="white", relief="flat", padx=12, pady=12, wrap="word")
        self.output.pack(fill="both", expand=True, pady=(10, 0))

        watched = [
            self.project, self.reference, self.texture, self.custom, self.strategy,
            self.planner_mode, self.planning_sample, self.source, self.catalog_region,
            self.real_slots, self.quality_bias, self.smart_quality,
        ]
        for variable in watched:
            variable.trace_add("write", self.schedule_auto_preview)
        self.auto_preview.trace_add("write", self.schedule_auto_preview)
        self.source.trace_add("write", self._update_filament_selection_summary)

    def combo(self, parent, title, variable, values, column, row=0):
        parent.columnconfigure(column, weight=1)
        ttk.Label(parent, text=title).grid(row=row * 2, column=column, sticky="w", padx=(0, 20), pady=(0, 2))
        ttk.Combobox(parent, textvariable=variable, values=values, state="readonly", width=13).grid(row=row * 2 + 1, column=column, sticky="ew", padx=(0, 12), pady=(0, 8))

    def _refresh_inventory(self):
        try:
            snapshot = ENGINE.read_bambu_inventory(required=False, minimum_colors=0)
        except Exception:
            snapshot = None
        self.after(0, lambda: self._finish_inventory_refresh(snapshot))

    def _finish_inventory_refresh(self, snapshot):
        self.inventory_snapshot = snapshot
        self._update_filament_selection_summary()

    def _filament_options(self):
        snapshot = self.inventory_snapshot
        source = self.source.get()
        if not snapshot or source not in ("inventory", "catalog", "all-bambu"):
            return []
        if source == "inventory":
            raw = [
                ENGINE.anchor_option_payload(item)
                for item in ENGINE.inventory_palette(snapshot)
            ]
        else:
            raw = list(snapshot.get("anchorOptions") or [])
            if source == "catalog":
                core = {"PLA Basic", "PLA Matte", "PLA Silk+"}
                raw = [item for item in raw if item.get("series") in core]
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

    def _update_filament_selection_summary(self, *_):
        source = self.source.get()
        if source not in ("inventory", "catalog", "all-bambu"):
            self.filament_selection_summary.set("Automatic for this filament source")
            return
        if self.inventory_snapshot is None:
            self.filament_selection_summary.set("Loading filament colors...")
            return
        options = self._filament_options()
        option_keys = {item["key"] for item in options}
        self.disabled_anchor_keys.intersection_update(option_keys)
        self.pinned_anchor_keys.intersection_update(option_keys)
        enabled = len(option_keys - self.disabled_anchor_keys)
        pins = len(self.pinned_anchor_keys)
        self.filament_selection_summary.set(
            f"{enabled} of {len(options)} enabled" + (f" | {pins} pinned" if pins else "")
        )

    def open_filament_selector(self):
        options = self._filament_options()
        if not options:
            if self.inventory_snapshot is None:
                messagebox.showinfo("Filament colors", "The Bambu Studio filament inventory is still loading.")
            else:
                messagebox.showinfo(
                    "Filament colors",
                    "Choose My Inventory, Bambu Core, or All Bambu to select individual colors.",
                )
            return

        dialog = tk.Toplevel(self)
        dialog.title("Filament Colors")
        dialog.geometry("650x650")
        dialog.minsize(520, 470)
        dialog.configure(bg="#151719")
        dialog.transient(self)
        dialog.grab_set()

        shell = ttk.Frame(dialog, padding=16)
        shell.pack(fill="both", expand=True)
        ttk.Label(shell, text="FILAMENT COLORS", style="Section.TLabel").pack(anchor="w")
        ttk.Label(
            shell,
            text="Enable colors the planner may use. Pin only colors that must occupy a physical slot.",
            style="Small.TLabel",
            wraplength=590,
            justify="left",
        ).pack(anchor="w", pady=(5, 12))

        toolbar = ttk.Frame(shell)
        toolbar.pack(fill="x", pady=(0, 9))
        search = tk.StringVar()
        ttk.Entry(toolbar, textvariable=search).pack(side="left", fill="x", expand=True)
        selected = {
            item["key"]: tk.BooleanVar(value=item["key"] not in self.disabled_anchor_keys)
            for item in options
        }
        pinned = {
            item["key"]: tk.BooleanVar(value=item["key"] in self.pinned_anchor_keys)
            for item in options
        }

        canvas = tk.Canvas(shell, bg="#151719", highlightthickness=1, highlightbackground="#30363a")
        scrollbar = ttk.Scrollbar(shell, orient="vertical", command=canvas.yview)
        rows = ttk.Frame(canvas, padding=(8, 6))
        window = canvas.create_window((0, 0), window=rows, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        rows.bind("<Configure>", lambda _: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window, width=event.width))
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def toggle_pin(key):
            if pinned[key].get():
                selected[key].set(True)

        def rebuild(*_):
            for child in rows.winfo_children():
                child.destroy()
            query = search.get().strip().lower()
            visible = [
                item for item in options
                if not query or query in str(item.get("name") or "").lower()
                or query in str(item.get("series") or "").lower()
                or query in str(item.get("color") or "").lower()
            ]
            for item in visible:
                key = item["key"]
                row = ttk.Frame(rows, padding=(2, 5))
                row.pack(fill="x")
                ttk.Checkbutton(row, variable=selected[key]).pack(side="left")
                swatch = tk.Frame(row, width=22, height=22, bg=item.get("color") or "#777777")
                swatch.pack(side="left", padx=(3, 9))
                swatch.pack_propagate(False)
                label = ttk.Frame(row)
                label.pack(side="left", fill="x", expand=True)
                ttk.Label(label, text=item.get("name") or key).pack(anchor="w")
                grams = item.get("remainingGrams")
                detail = (
                    f"{item.get('series', '')} | {item.get('color', '')} | {grams:.0f} g remaining"
                    if grams is not None else
                    f"{item.get('series', '')} | {item.get('color', '')} | catalog color"
                )
                ttk.Label(label, text=detail, style="Small.TLabel").pack(anchor="w")
                ttk.Checkbutton(
                    row, text="Pin", variable=pinned[key], command=lambda value=key: toggle_pin(value)
                ).pack(side="right", padx=(8, 2))
            if not visible:
                ttk.Label(rows, text="No matching filament colors.", style="Small.TLabel").pack(pady=24)

        search.trace_add("write", rebuild)
        rebuild()

        footer = ttk.Frame(dialog, padding=(16, 0, 16, 16))
        footer.pack(fill="x")

        def select_all():
            for value in selected.values():
                value.set(True)

        def clear_pins():
            for value in pinned.values():
                value.set(False)

        def apply_selection():
            enabled = {key for key, value in selected.items() if value.get()}
            colors = {item.get("color") for item in options if item["key"] in enabled}
            if len(colors) < 2:
                messagebox.showerror("Filament colors", "Enable at least two distinct filament colors.", parent=dialog)
                return
            selected_pins = {key for key, value in pinned.items() if value.get()} & enabled
            maximum = int(self.real_slots.get()) if self.real_slots.get().isdigit() else 6
            if len(selected_pins) > maximum:
                messagebox.showerror(
                    "Filament colors",
                    f"This plan allows at most {maximum} pinned physical colors.",
                    parent=dialog,
                )
                return
            all_keys = {item["key"] for item in options}
            self.disabled_anchor_keys = all_keys - enabled
            self.pinned_anchor_keys = selected_pins
            self._update_filament_selection_summary()
            dialog.destroy()
            self.schedule_auto_preview()

        ttk.Button(footer, text="All", command=select_all).pack(side="left")
        ttk.Button(footer, text="Clear Pins", command=clear_pins).pack(side="left", padx=(8, 0))
        ttk.Button(footer, text="Cancel", command=dialog.destroy).pack(side="right")
        ttk.Button(footer, text="Apply", command=apply_selection, style="Accent.TButton").pack(side="right", padx=(0, 8))

    def schedule_auto_preview(self, *_):
        self.settings_revision += 1
        if self.auto_preview_after is not None:
            self.after_cancel(self.auto_preview_after)
            self.auto_preview_after = None
        if not self.auto_preview.get():
            self.auto_preview_dirty = False
            return
        source = Path(self.project.get())
        if not source.is_file() or source.suffix.lower() not in (".3mf", ".obj", ".glb"):
            return
        if self.source.get() == "custom" and not Path(self.custom.get()).is_file():
            return
        if self.worker_active:
            self.auto_preview_dirty = True
            return
        self.auto_preview_dirty = False
        revision = self.settings_revision
        self.status.set("Live forecast queued for the current choices.")
        self.auto_preview_after = self.after(
            750,
            lambda: self.start_operation(plan_only=True, automatic=True, operation_revision=revision),
        )

    def _draw_accuracy(self, score, empty=False):
        canvas = self.accuracy_canvas
        canvas.delete("all")
        canvas.create_arc(10, 10, 102, 102, start=90, extent=-359.9, style="arc", width=9, outline="#2b3033")
        if not empty:
            color = "#58c488" if score >= 88 else ("#55bdcf" if score >= 70 else "#eba85e")
            canvas.create_arc(10, 10, 102, 102, start=90, extent=-359.9 * max(0, min(100, score)) / 100, style="arc", width=9, outline=color)
        canvas.create_text(56, 51, text="--%" if empty else f"{round(score):.0f}%", fill="#f1f5f5", font=("Segoe UI", 18, "bold"))
        canvas.create_text(56, 72, text="accuracy", fill="#88959b", font=("Segoe UI", 8, "bold"))

    def _draw_palette(self, colors):
        self.palette_canvas.delete("all")
        if not colors:
            self.palette_canvas.configure(height=44)
            self.palette_canvas.create_text(6, 22, anchor="w", text="No forecast palette", fill="#768187", font=("Segoe UI", 10))
            return
        width = max(320, self.palette_canvas.winfo_width())
        gap = 5
        columns = min(16, len(colors))
        rows = (len(colors) + columns - 1) // columns
        swatch_width = max(18, (width - gap * (columns - 1)) / columns)
        self.palette_canvas.configure(height=8 + rows * 33 + max(0, rows - 1) * gap)
        for index, color in enumerate(colors):
            if not isinstance(color, str) or len(color) != 7 or not color.startswith("#"):
                continue
            column = index % columns
            row = index // columns
            x0 = column * (swatch_width + gap)
            y0 = 4 + row * (33 + gap)
            self.palette_canvas.create_rectangle(x0, y0, x0 + swatch_width, y0 + 33, fill=color, outline="#4a5155", width=1)

    def update_forecast(self, result):
        self.last_plan_result = result
        forecast = plan_forecast(result)
        score = forecast["accuracy"]
        confidence = forecast["confidence"]
        maximum = forecast["maximumDeltaE"]
        self.accuracy_value.set(f"{score:.0f}%")
        self.confidence_value.set(f"{confidence:.0f}%")
        self.error_value.set(f"dE {maximum:.1f}")
        self.slots_value.set(forecast["slotSummary"])
        self._draw_accuracy(score)
        self._draw_palette(forecast["colors"])

        suggestion = forecast["suggestion"]
        self.forecast_suggestion = suggestion
        self.suggestion_button.configure(state="normal" if suggestion else "disabled")
        self.gap_message.set(forecast["gapMessage"])

    def use_forecast_suggestion(self):
        suggestion = getattr(self, "forecast_suggestion", None)
        if not suggestion:
            return
        if suggestion.get("availability") == "not in My Inventory":
            self.source.set("all-bambu")
        else:
            self.planner_mode.set("best")
        key = suggestion.get("key")
        if key:
            self.disabled_anchor_keys.discard(key)
            self.pinned_anchor_keys.add(key)
            self._update_filament_selection_summary()
        self.schedule_auto_preview()

    def load_source_thumbnail(self, path):
        source = Path(path)
        if source.suffix.lower() != ".3mf":
            self._show_preview_message("Textured source selected\nForecast palette will appear after planning")
            return
        destination = Path(tempfile.gettempdir()) / f"fullspectrum-source-{time.time_ns()}.png"

        def worker():
            try:
                inspected = ENGINE.inspect_project(source, thumbnail_dest=destination, metadata_only=True)
                thumbnail = inspected.get("thumbnail")
                def display_thumbnail():
                    if self.project.get() == str(source):
                        self._show_source_thumbnail(thumbnail)
                    elif thumbnail:
                        Path(thumbnail).unlink(missing_ok=True)
                self.after(0, display_thumbnail)
            except Exception:
                destination.unlink(missing_ok=True)
                self.after(
                    0,
                    lambda: self._show_preview_message("Source loaded\nPreview image unavailable")
                    if self.project.get() == str(source) else None,
                )

        threading.Thread(target=worker, daemon=True).start()

    def _show_source_thumbnail(self, path):
        if not path or not Path(path).is_file():
            self._show_preview_message("Source loaded\nPreview image unavailable")
            return
        try:
            with Image.open(path) as source_image:
                image = source_image.convert("RGB")
            width = max(420, self.preview_canvas.winfo_width() - 24)
            image.thumbnail((width, 276), Image.Resampling.LANCZOS)
            self.source_preview_photo = ImageTk.PhotoImage(image)
            self.preview_canvas.delete("all")
            self.preview_canvas.create_image(
                max(210, self.preview_canvas.winfo_width() / 2),
                150,
                image=self.source_preview_photo,
            )
        except Exception:
            self._show_preview_message("Source loaded\nPreview image unavailable")
        finally:
            Path(path).unlink(missing_ok=True)

    def _show_preview_message(self, message):
        self.source_preview_photo = None
        self.preview_canvas.delete("all")
        self.preview_canvas.create_text(
            max(210, self.preview_canvas.winfo_width() / 2), 150,
            text=message, fill="#768187", font=("Segoe UI", 12), justify="center",
        )

    def choose_project(self):
        path = filedialog.askopenfilename(filetypes=[("FullSpectrum sources", "*.3mf *.obj *.glb"), ("Bambu 3MF", "*.3mf"), ("Textured model", "*.obj *.glb")])
        if path:
            if self.project.get() != path:
                self.texture.set("")
            self.project.set(path)
            self.load_source_thumbnail(path)

    def choose_reference(self):
        path = filedialog.askopenfilename(filetypes=[("Reference assets", "*.obj *.glb *.png *.jpg *.jpeg *.bmp *.tif *.tiff")])
        if path:
            self.reference.set(path)

    def choose_texture(self):
        path = filedialog.askopenfilename(filetypes=[("Base-color texture", "*.png *.jpg *.jpeg")])
        if path:
            self.texture.set(path)

    def choose_custom(self):
        path = filedialog.askopenfilename(filetypes=[("JSON filament library", "*.json")])
        if path:
            self.custom.set(path)
            self.source.set("custom")

    def preview_plan(self):
        self.start_operation(plan_only=True)

    def convert(self):
        self.start_operation(plan_only=False)

    def start_operation(self, plan_only, automatic=False, operation_revision=None):
        self.auto_preview_after = None
        if self.worker_active:
            if automatic:
                self.auto_preview_dirty = True
            return
        source = Path(self.project.get())
        if not source.is_file() or source.suffix.lower() not in (".3mf", ".obj", ".glb"):
            if not automatic:
                messagebox.showerror("FullSpectrum Studio", "Choose a painted Bambu .3mf or textured OBJ / GLB source first.")
            return
        if self.source.get() == "custom" and not Path(self.custom.get()).is_file():
            if not automatic:
                messagebox.showerror("FullSpectrum Studio", "Choose a custom filament JSON library.")
            return
        self.preview_button.configure(state="disabled")
        self.convert_button.configure(state="disabled")
        self.cancel_button.configure(state="normal")
        self.folder_button.configure(state="disabled")
        self.copy_error_button.configure(state="disabled")
        if not automatic:
            self.output.delete("1.0", "end")
        self.progress.set(0)
        self.cancel_requested = False
        self.worker_active = True
        self.last_error_report = ""
        self.last_error_log = None
        self.operation_name = "Plan preview" if plan_only else "Conversion"
        self.record_progress(0, "Updating live forecast." if automatic else ("Starting plan preview." if plan_only else "Starting conversion."))
        self.start_heartbeat()
        operation_revision = self.settings_revision if operation_revision is None else operation_revision
        filament_options = self._filament_options()
        option_keys = {item["key"] for item in filament_options}
        disabled_keys = self.disabled_anchor_keys & option_keys
        options = {
            "strategy": self.strategy.get(),
            "source": self.source.get(),
            "catalog_region": self.catalog_region.get(),
            "planner_mode": self.planner_mode.get(),
            "planning_sample": self.planning_sample.get(),
            "real_slots": self.real_slots.get(),
            "quality_bias": "auto" if self.smart_quality.get() else self.quality_bias.get(),
            "mix_model": self.mix_model.get(),
            "reference": self.reference.get() or None,
            "texture": self.texture.get() or None,
            "custom": self.custom.get() or None,
            "auto_open": self.auto_open.get(),
            "output_application": self.output_application.get(),
            "allowed_anchor_keys": sorted(option_keys - disabled_keys) if disabled_keys else None,
            "pinned_anchor_keys": sorted(self.pinned_anchor_keys & option_keys),
        }
        threading.Thread(
            target=self._run_operation,
            args=(source, options, plan_only, automatic, operation_revision),
            daemon=True,
        ).start()

    def _run_operation(self, source, options, plan_only, automatic, operation_revision):
        def report(fraction, message):
            if self.cancel_requested:
                raise RuntimeError("Operation cancelled by user.")
            self.last_progress_time = time.monotonic()
            self.last_engine_message = message
            self.after(0, lambda: self.record_progress(fraction, message))
        try:
            result = ENGINE.convert(
                source,
                options["strategy"],
                palette_source=options["source"],
                output_dir=source.parent,
                reveal=False,
                real_slots=options["real_slots"],
                reference=options["reference"],
                custom_catalog_path=options["custom"],
                texture_override=options["texture"],
                quality_bias=options["quality_bias"],
                catalog_region=options["catalog_region"],
                planner_mode=options["planner_mode"],
                planning_sample=options["planning_sample"],
                mix_model=options["mix_model"],
                plan_only=plan_only,
                allowed_anchor_keys=options["allowed_anchor_keys"],
                pinned_anchor_keys=options["pinned_anchor_keys"],
                progress=report,
            )
            if plan_only:
                text = format_plan_preview(result)
                self.after(0, lambda: self.finish_plan(result, text, automatic, operation_revision))
                return
            text = [
                f"Validated output: {result['output']}",
                f"Physical slots: {result['realSlots']}   Mixed slots: {result['outputSlots'] - result['realSlots']}",
                f"Quality/waste: {result.get('qualityBiasMode', 'manual')} {result.get('qualityBias', options['quality_bias'])}",
                f"Planner: {result.get('plannerMode', options['planner_mode'])}",
                f"Catalog planning region: {result.get('catalogRegionLabel', options['catalog_region'])}",
                f"Quality: {result['quality']['qualityScore']:.1f} / 100   Mean dE: {result['quality']['estimatedDeltaE']:.2f}   Max dE: {result['quality']['maximumDeltaE']:.2f}",
                f"Confidence: {result['quality']['confidenceScore']:.1f} / 100   Contrast: {result['quality'].get('contrastRetention', 0):.1f}%",
                f"Bambu color synchronization: dE {result['colorValidation']['maximumDeltaE']:.2f} max (verified)",
                f"Printability: {result['printability']['difficulty']}   Mixed paint: {result['printability']['paintedMixedShare']:.1f}%",
                "Geometry, textures and decoded paint remap: verified",
                "Actual time and filament usage require slicing in Bambu Studio.",
            ]
            text.extend(f"Suggestion: {suggestion}" for suggestion in result["printability"]["recommendations"])
            text.extend(f"Warning: {warning}" for warning in result["warnings"])
            self.last_output = result["output"]
            self.after(0, lambda: self.finish(result, "\n".join(text)))
            if options["auto_open"]:
                self.open_validated_output(result["output"], options["output_application"])
        except Exception as error:
            details = "".join(traceback.format_exception(type(error), error, error.__traceback__))
            self.after(0, lambda: self.fail(str(error) or error.__class__.__name__, details, quiet=automatic))

    def finish(self, result, text):
        self.worker_active = False
        self.inventory_snapshot = result.get("inventory") or self.inventory_snapshot
        self._update_filament_selection_summary()
        self.preview_button.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.insert("1.0", text)
        self.update_forecast(result)
        self.status.set("Conversion validated and ready.")
        self.progress.set(100)
        self.convert_button.configure(state="normal")
        self.cancel_button.configure(state="disabled")
        self.folder_button.configure(state="normal")
        self._resume_auto_preview_if_needed()

    def finish_plan(self, result, text, automatic=False, operation_revision=None):
        self.worker_active = False
        self.preview_button.configure(state="normal")
        self.convert_button.configure(state="normal")
        self.cancel_button.configure(state="disabled")
        self.folder_button.configure(state="disabled")
        if automatic and operation_revision != self.settings_revision:
            self.status.set(
                "Choices changed. Refreshing the live forecast."
                if self.auto_preview.get() else "Automatic forecast paused."
            )
            self._resume_auto_preview_if_needed(force=True)
            return
        self.output.delete("1.0", "end")
        self.output.insert("1.0", text)
        self.update_forecast(result)
        self.status.set(
            f"Live forecast ready: {result['quality']['qualityScore']:.0f}% estimated accuracy."
            if automatic else "Plan preview ready. No 3MF was written."
        )
        self.progress.set(100)
        self._resume_auto_preview_if_needed()

    def fail(self, message, details=None, quiet=False):
        self.worker_active = False
        if self.cancel_requested:
            self.status.set(f"{self.operation_name} cancelled.")
            self.preview_button.configure(state="normal")
            self.convert_button.configure(state="normal")
            self.cancel_button.configure(state="disabled")
            self._resume_auto_preview_if_needed()
            return
        suffix = "cancelled." if self.cancel_requested else "failed."
        self.status.set(f"{self.operation_name} {suffix}")
        self.preview_button.configure(state="normal")
        self.convert_button.configure(state="normal")
        self.cancel_button.configure(state="disabled")
        self.copy_error_button.configure(state="normal")
        self.output.delete("1.0", "end")
        report = self.build_error_report(message, details)
        self.output.insert("1.0", report)
        if not quiet:
            messagebox.showerror("FullSpectrum Studio", privacy_safe_error_message(message))
        self._resume_auto_preview_if_needed()

    def _resume_auto_preview_if_needed(self, force=False):
        should_resume = force or self.auto_preview_dirty
        self.auto_preview_dirty = False
        if should_resume and self.auto_preview.get():
            self.schedule_auto_preview()

    def cancel_conversion(self):
        self.cancel_requested = True
        self.status.set("Cancelling at the next safe engine checkpoint...")

    def record_progress(self, fraction, message):
        self.progress.set(fraction * 100)
        self.status.set(message)

    def start_heartbeat(self):
        self.after(5000, self.check_heartbeat)

    def check_heartbeat(self):
        if not self.worker_active:
            return
        if self.cancel_requested:
            self.status.set("Cancelling at the next safe engine checkpoint...")
        else:
            idle = time.monotonic() - self.last_progress_time
            if idle >= 90:
                self.status.set(f"Possibly stuck at: {self.last_engine_message}")
            elif idle >= 20:
                self.status.set(f"Still working: {self.last_engine_message}")
        self.after(5000, self.check_heartbeat)

    def build_error_report(self, message, details=None):
        private_body = "\n".join([
            "FullSpectrum Studio conversion error",
            "",
            message,
            "",
            details or message,
        ])
        self.last_error_log = self.write_debug_log(private_body)
        self.last_error_report = format_shareable_error_report(
            message,
            log_created=self.last_error_log is not None,
        )
        return self.last_error_report

    def write_debug_log(self, report):
        try:
            if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
                root = Path(os.environ["LOCALAPPDATA"]) / "FullSpectrumStudio" / "Logs"
            elif sys.platform == "darwin":
                root = Path.home() / "Library" / "Logs" / "FullSpectrumStudio"
            else:
                root = Path.home() / ".cache" / "FullSpectrumStudio" / "Logs"
            root.mkdir(parents=True, exist_ok=True)
            path = root / f"conversion-{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"
            path.write_text(
                "\n".join([
                    "FullSpectrum Studio desktop debug log",
                    f"Created: {datetime.now(timezone.utc).isoformat()}",
                    "",
                    report,
                ]),
                encoding="utf-8",
            )
            return path
        except Exception:
            return None

    def copy_error_report(self):
        if not self.last_error_report:
            return
        self.clipboard_clear()
        self.clipboard_append(self.last_error_report)
        self.status.set("Privacy-safe error report copied.")

    def open_folder(self):
        if not hasattr(self, "last_output"):
            return
        output = str(Path(self.last_output))
        if os.name == "nt":
            subprocess.Popen(["explorer", "/select,", output])
        else:
            subprocess.run(["open", "-R", output])

    def open_validated_output(self, output, application):
        if application != "OrcaSlicer":
            os.startfile(output) if os.name == "nt" else subprocess.run(["open", output])
            return
        if os.name == "nt":
            possible = [
                Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "OrcaSlicer" / "orca-slicer.exe",
                Path(os.environ.get("ProgramFiles", "")) / "OrcaSlicer" / "orca-slicer.exe",
                Path(os.environ.get("ProgramFiles", "")) / "OrcaSlicer" / "OrcaSlicer.exe",
            ]
            executable = next((str(path) for path in possible if path.is_file()), None) or shutil.which("orca-slicer")
            if executable:
                subprocess.Popen([executable, output])
                return
        elif shutil.which("open") and subprocess.run(["open", "-Ra", "OrcaSlicer"]).returncode == 0:
            subprocess.Popen(["open", "-a", "OrcaSlicer", output])
            return
        self.after(0, lambda: messagebox.showwarning(
            "OrcaSlicer not found",
            "The validated output was saved, but OrcaSlicer was not found. Install OrcaSlicer or open the .3mf manually."
        ))


if __name__ == "__main__":
    StudioApp().mainloop()
