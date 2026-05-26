#!/usr/bin/env python3
"""Cross-platform FullSpectrum Studio desktop shell for the shared engine."""

import importlib.util
import os
import subprocess
import sys
import threading
import tkinter as tk
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
        self.custom = tk.StringVar()
        self.strategy = tk.StringVar(value="official")
        self.source = tk.StringVar(value="inventory")
        self.real_slots = tk.StringVar(value="auto")
        self.auto_open = tk.BooleanVar(value=True)
        self.progress = tk.DoubleVar(value=0)
        self.status = tk.StringVar(value="Choose a painted Bambu .3mf to begin.")
        self._build()

    def _build(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", background="#101721", foreground="#e9f0f5", fieldbackground="#182331")
        style.configure("TButton", padding=8)
        style.configure("Title.TLabel", font=("Segoe UI", 22, "bold"), foreground="#f6fbff")
        style.configure("Small.TLabel", foreground="#9cb4c5")
        frame = ttk.Frame(self, padding=24)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="FullSpectrum Studio", style="Title.TLabel").pack(anchor="w")
        ttk.Label(frame, text="Local reduced-filament workflow for painted Bambu projects", style="Small.TLabel").pack(anchor="w", pady=(0, 22))

        for title, variable, action in [
            ("Painted 3MF project", self.project, self.choose_project),
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
        self.combo(choices, "Strategy", self.strategy, ["official", "cmykw"], 0)
        self.combo(choices, "Filaments", self.source, ["inventory", "catalog", "all-bambu", "custom", "exact-cmykw"], 1)
        self.combo(choices, "Physical slots", self.real_slots, ["auto", "2", "3", "4", "5", "6"], 2)
        ttk.Checkbutton(choices, text="Open validated output", variable=self.auto_open).grid(row=1, column=3, padx=(24, 0), sticky="w")

        ttk.Progressbar(frame, variable=self.progress, maximum=100).pack(fill="x", pady=(8, 10))
        ttk.Label(frame, textvariable=self.status, style="Small.TLabel").pack(anchor="w")
        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=18)
        self.convert_button = ttk.Button(buttons, text="Convert and Validate", command=self.convert)
        self.convert_button.pack(side="left")
        ttk.Button(buttons, text="Open Output Folder", command=self.open_folder).pack(side="left", padx=8)
        self.output = tk.Text(frame, height=14, bg="#121c28", fg="#d7e5ed", insertbackground="white", relief="flat", padx=12, pady=12)
        self.output.pack(fill="both", expand=True)

    def combo(self, parent, title, variable, values, column):
        ttk.Label(parent, text=title).grid(row=0, column=column, sticky="w", padx=(0, 20))
        ttk.Combobox(parent, textvariable=variable, values=values, state="readonly", width=18).grid(row=1, column=column, sticky="w", padx=(0, 20), pady=4)

    def choose_project(self):
        path = filedialog.askopenfilename(filetypes=[("Bambu 3MF", "*.3mf")])
        if path:
            self.project.set(path)

    def choose_reference(self):
        path = filedialog.askopenfilename(filetypes=[("Reference assets", "*.obj *.glb *.png *.jpg *.jpeg *.bmp *.tif *.tiff")])
        if path:
            self.reference.set(path)

    def choose_custom(self):
        path = filedialog.askopenfilename(filetypes=[("JSON filament library", "*.json")])
        if path:
            self.custom.set(path)
            self.source.set("custom")

    def convert(self):
        source = Path(self.project.get())
        if not source.is_file() or source.suffix.lower() != ".3mf":
            messagebox.showerror("FullSpectrum Studio", "Choose a painted Bambu .3mf project first.")
            return
        if self.source.get() == "custom" and not Path(self.custom.get()).is_file():
            messagebox.showerror("FullSpectrum Studio", "Choose a custom filament JSON library.")
            return
        self.convert_button.configure(state="disabled")
        self.output.delete("1.0", "end")
        self.progress.set(0)
        options = {
            "strategy": self.strategy.get(),
            "source": self.source.get(),
            "real_slots": self.real_slots.get(),
            "reference": self.reference.get() or None,
            "custom": self.custom.get() or None,
            "auto_open": self.auto_open.get(),
        }
        threading.Thread(target=self._run_conversion, args=(source, options), daemon=True).start()

    def _run_conversion(self, source, options):
        def report(fraction, message):
            self.after(0, lambda: (self.progress.set(fraction * 100), self.status.set(message)))
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
                progress=report,
            )
            text = [
                f"Validated output: {result['output']}",
                f"Physical slots: {result['realSlots']}   Mixed slots: {result['outputSlots'] - result['realSlots']}",
                f"Quality: {result['quality']['qualityScore']:.1f} / 100   Mean dE: {result['quality']['estimatedDeltaE']:.2f}",
                "Geometry/textures: verified unchanged",
            ]
            text.extend(f"Warning: {warning}" for warning in result["warnings"])
            self.last_output = result["output"]
            self.after(0, lambda: self.finish("\n".join(text)))
            if options["auto_open"]:
                os.startfile(result["output"]) if os.name == "nt" else subprocess.run(["open", result["output"]])
        except Exception as error:
            self.after(0, lambda: self.fail(str(error)))

    def finish(self, text):
        self.output.insert("1.0", text)
        self.status.set("Conversion validated and ready.")
        self.progress.set(100)
        self.convert_button.configure(state="normal")

    def fail(self, message):
        self.status.set("Conversion failed.")
        self.convert_button.configure(state="normal")
        messagebox.showerror("FullSpectrum Studio", message)

    def open_folder(self):
        if not hasattr(self, "last_output"):
            return
        folder = str(Path(self.last_output).parent)
        os.startfile(folder) if os.name == "nt" else subprocess.run(["open", folder])


if __name__ == "__main__":
    StudioApp().mainloop()
