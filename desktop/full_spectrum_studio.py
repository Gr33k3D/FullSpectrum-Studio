#!/usr/bin/env python3
"""Cross-platform FullSpectrum Studio desktop shell for the shared engine."""

import importlib.util
import os
import shutil
import subprocess
import sys
import threading
import time
import traceback
import tkinter as tk
from datetime import datetime, timezone
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


def load_engine():
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    engine_path = root / "fullspectrum_engine.py"
    spec = importlib.util.spec_from_file_location("fullspectrum_engine", engine_path)
    engine = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(engine)
    return engine


ENGINE = load_engine()


class StudioApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("FullSpectrum Studio")
        self.geometry("980x690")
        self.minsize(820, 560)
        self.configure(bg="#101721")
        self.project = tk.StringVar()
        self.reference = tk.StringVar()
        self.texture = tk.StringVar()
        self.custom = tk.StringVar()
        self.strategy = tk.StringVar(value="official")
        self.planner_mode = tk.StringVar(value="best")
        self.source = tk.StringVar(value="inventory")
        self.catalog_region = tk.StringVar(value="global")
        self.real_slots = tk.StringVar(value="auto")
        self.mix_model = tk.StringVar(value="bambu")
        self.quality_bias = tk.IntVar(value=60)
        self.smart_quality = tk.BooleanVar(value=True)
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
        self._build()

    def _build(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", background="#101721", foreground="#e9f0f5", fieldbackground="#182331")
        style.configure("TButton", padding=8, foreground="#f6fbff", background="#233041")
        style.map("TButton", foreground=[("active", "#ffffff"), ("pressed", "#ffffff"), ("disabled", "#7f91a0")], background=[("active", "#2f4056"), ("pressed", "#1d2a3a")])
        style.configure("TCombobox", foreground="#f6fbff", fieldbackground="#182331", background="#233041", arrowcolor="#f6fbff")
        style.map("TCombobox", foreground=[("readonly", "#f6fbff")], fieldbackground=[("readonly", "#182331")], selectforeground=[("readonly", "#f6fbff")], selectbackground=[("readonly", "#182331")])
        style.configure("Title.TLabel", font=("Segoe UI", 22, "bold"), foreground="#f6fbff")
        style.configure("Small.TLabel", foreground="#9cb4c5")
        frame = ttk.Frame(self, padding=24)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="FullSpectrum Studio", style="Title.TLabel").pack(anchor="w")
        ttk.Label(frame, text="Local reduced-filament workflow for painted Bambu projects", style="Small.TLabel").pack(anchor="w", pady=(0, 22))
        ttk.Label(
            frame,
            text="Reduces/remaps existing Bambu paint states. It does not repaint, smooth or clean up painted regions.",
            style="Small.TLabel",
        ).pack(anchor="w", pady=(0, 12))

        for title, variable, action in [
            ("Painted 3MF project or textured OBJ / GLB (experimental)", self.project, self.choose_project),
            ("OBJ base-color texture override (PNG / JPG)", self.texture, self.choose_texture),
            ("Optional OBJ / GLB / texture reference", self.reference, self.choose_reference),
            ("Optional custom filament library (JSON)", self.custom, self.choose_custom),
        ]:
            ttk.Label(frame, text=title).pack(anchor="w", pady=(8, 3))
            row = ttk.Frame(frame)
            row.pack(fill="x")
            ttk.Entry(row, textvariable=variable).pack(side="left", fill="x", expand=True)
            ttk.Button(row, text="Browse", command=action).pack(side="left", padx=(8, 0))

        choices = ttk.Frame(frame)
        choices.pack(fill="x", pady=22)
        self.combo(choices, "Strategy", self.strategy, ["official", "cmykw"], 0, 0)
        self.combo(choices, "Planner", self.planner_mode, ["best", "fast"], 1, 0)
        self.combo(choices, "Filaments", self.source, ["inventory", "catalog", "all-bambu", "custom", "exact-cmykw"], 2, 0)
        self.combo(choices, "Physical slots", self.real_slots, ["auto", "2", "3", "4", "5", "6", "7", "8"], 0, 1)
        self.combo(choices, "Catalog region", self.catalog_region, ["global", "eu", "us-ca", "uk", "au-nz", "asia"], 1, 1)
        ttk.Label(
            frame,
            text="Catalog region is planning metadata only; FullSpectrum does not check live Bambu store stock.",
            style="Small.TLabel",
        ).pack(anchor="w", pady=(0, 12))
        handoff = ttk.Frame(frame)
        handoff.pack(fill="x", pady=(0, 12))
        ttk.Checkbutton(handoff, text="Open validated output in", variable=self.auto_open).pack(side="left")
        ttk.Combobox(
            handoff, textvariable=self.output_application,
            values=["Bambu Studio", "OrcaSlicer"], state="readonly", width=18
        ).pack(side="left", padx=(8, 0))
        ttk.Label(handoff, text="Validates first, then hands the file to the slicer.", style="Small.TLabel").pack(side="left", padx=(14, 0))

        slider = ttk.Frame(frame)
        slider.pack(fill="x", pady=(0, 16))
        ttk.Checkbutton(slider, text="Smart quality", variable=self.smart_quality).pack(side="left")
        tk.Scale(
            slider, from_=0, to=100, orient="horizontal", variable=self.quality_bias,
            bg="#101721", fg="#d7e5ed", highlightthickness=0, troughcolor="#182331",
            length=320
        ).pack(side="left", padx=12)
        ttk.Label(slider, text="Best planner searches dense 2/3-color mixes; Fast keeps the quicker planner. 7/8 slots are experimental.", style="Small.TLabel").pack(side="left")

        ttk.Progressbar(frame, variable=self.progress, maximum=100).pack(fill="x", pady=(8, 10))
        ttk.Label(frame, textvariable=self.status, style="Small.TLabel").pack(anchor="w")
        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=18)
        self.convert_button = ttk.Button(buttons, text="Convert and Validate", command=self.convert)
        self.convert_button.pack(side="left")
        self.cancel_button = ttk.Button(buttons, text="Cancel", command=self.cancel_conversion, state="disabled")
        self.cancel_button.pack(side="left", padx=8)
        self.folder_button = ttk.Button(buttons, text="Show Output", command=self.open_folder, state="disabled")
        self.folder_button.pack(side="left", padx=8)
        self.copy_error_button = ttk.Button(buttons, text="Copy Error Report", command=self.copy_error_report, state="disabled")
        self.copy_error_button.pack(side="left", padx=8)
        self.output = tk.Text(frame, height=14, bg="#121c28", fg="#d7e5ed", insertbackground="white", relief="flat", padx=12, pady=12)
        self.output.pack(fill="both", expand=True)

    def combo(self, parent, title, variable, values, column, row=0):
        ttk.Label(parent, text=title).grid(row=row * 2, column=column, sticky="w", padx=(0, 20), pady=(0, 2))
        ttk.Combobox(parent, textvariable=variable, values=values, state="readonly", width=18).grid(row=row * 2 + 1, column=column, sticky="w", padx=(0, 20), pady=(0, 8))

    def choose_project(self):
        path = filedialog.askopenfilename(filetypes=[("FullSpectrum sources", "*.3mf *.obj *.glb"), ("Bambu 3MF", "*.3mf"), ("Textured model", "*.obj *.glb")])
        if path:
            if self.project.get() != path:
                self.texture.set("")
            self.project.set(path)

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

    def convert(self):
        source = Path(self.project.get())
        if not source.is_file() or source.suffix.lower() not in (".3mf", ".obj", ".glb"):
            messagebox.showerror("FullSpectrum Studio", "Choose a painted Bambu .3mf or textured OBJ / GLB source first.")
            return
        if self.source.get() == "custom" and not Path(self.custom.get()).is_file():
            messagebox.showerror("FullSpectrum Studio", "Choose a custom filament JSON library.")
            return
        self.convert_button.configure(state="disabled")
        self.cancel_button.configure(state="normal")
        self.copy_error_button.configure(state="disabled")
        self.output.delete("1.0", "end")
        self.progress.set(0)
        self.cancel_requested = False
        self.worker_active = True
        self.last_error_report = ""
        self.last_error_log = None
        self.record_progress(0, "Starting conversion.")
        self.start_heartbeat()
        options = {
            "strategy": self.strategy.get(),
            "source": self.source.get(),
            "catalog_region": self.catalog_region.get(),
            "planner_mode": self.planner_mode.get(),
            "real_slots": self.real_slots.get(),
            "quality_bias": "auto" if self.smart_quality.get() else self.quality_bias.get(),
            "mix_model": self.mix_model.get(),
            "reference": self.reference.get() or None,
            "texture": self.texture.get() or None,
            "custom": self.custom.get() or None,
            "auto_open": self.auto_open.get(),
            "output_application": self.output_application.get(),
        }
        threading.Thread(target=self._run_conversion, args=(source, options), daemon=True).start()

    def _run_conversion(self, source, options):
        def report(fraction, message):
            if self.cancel_requested:
                raise RuntimeError("Conversion cancelled by user.")
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
                mix_model=options["mix_model"],
                progress=report,
            )
            text = [
                f"Validated output: {result['output']}",
                f"Physical slots: {result['realSlots']}   Mixed slots: {result['outputSlots'] - result['realSlots']}",
                f"Quality/waste: {result.get('qualityBiasMode', 'manual')} {result.get('qualityBias', options['quality_bias'])}",
                f"Planner: {result.get('plannerMode', options['planner_mode'])}",
                f"Catalog planning region: {result.get('catalogRegionLabel', options['catalog_region'])}",
                f"Quality: {result['quality']['qualityScore']:.1f} / 100   Mean dE: {result['quality']['estimatedDeltaE']:.2f}",
                f"Confidence: {result['quality']['confidenceScore']:.1f} / 100   Contrast: {result['quality'].get('contrastRetention', 0):.1f}%",
                f"Bambu color synchronization: dE {result['colorValidation']['maximumDeltaE']:.2f} max (verified)",
                f"Printability: {result['printability']['difficulty']}   Mixed paint: {result['printability']['paintedMixedShare']:.1f}%",
                "Geometry, textures and decoded paint remap: verified",
                "Actual time and filament usage require slicing in Bambu Studio.",
            ]
            text.extend(f"Suggestion: {suggestion}" for suggestion in result["printability"]["recommendations"])
            text.extend(f"Warning: {warning}" for warning in result["warnings"])
            self.last_output = result["output"]
            self.after(0, lambda: self.finish("\n".join(text)))
            if options["auto_open"]:
                self.open_validated_output(result["output"], options["output_application"])
        except Exception as error:
            details = "".join(traceback.format_exception(type(error), error, error.__traceback__))
            self.after(0, lambda: self.fail(str(error) or error.__class__.__name__, details))

    def finish(self, text):
        self.worker_active = False
        self.output.insert("1.0", text)
        self.status.set("Conversion validated and ready.")
        self.progress.set(100)
        self.convert_button.configure(state="normal")
        self.cancel_button.configure(state="disabled")
        self.folder_button.configure(state="normal")

    def fail(self, message, details=None):
        self.worker_active = False
        self.status.set("Conversion cancelled." if self.cancel_requested else "Conversion failed.")
        self.convert_button.configure(state="normal")
        self.cancel_button.configure(state="disabled")
        self.copy_error_button.configure(state="normal")
        self.output.delete("1.0", "end")
        report = self.build_error_report(message, details)
        self.output.insert("1.0", report)
        messagebox.showerror("FullSpectrum Studio", message)

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
        body = "\n".join([
            "FullSpectrum Studio conversion error",
            "",
            message,
            "",
            details or message,
        ])
        self.last_error_log = self.write_debug_log(body)
        if self.last_error_log:
            body = "\n".join([body, "", f"Debug log: {self.last_error_log}"])
        self.last_error_report = body
        return body

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
        self.status.set("Error report copied.")

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
