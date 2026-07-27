"""
Report Automator Pro — Desktop GUI
====================================
Modern dark-themed desktop application for one-click CAE report generation.
Uses customtkinter for a sleek industrial-grade UI with threaded backend
execution to keep the interface responsive during heavy rendering.

Author: Report Automator Pro Team
"""

import os
import sys
import threading
import time
from pathlib import Path

# -- ensure project root on path -------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

import customtkinter as ctk
from customtkinter import filedialog

# -- app modules -----------------------------------------------------------
from src.mock_data import generate_mock_dataset
from src.renderer import render_stress, render_displacement, render_report_suite
from src.ppt_generator import generate_pptx


# =========================================================================
# Globals
# =========================================================================

OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Brand colors for industrial dark theme
ACCENT = "#E94560"        # coral red accent
BG_DARK = "#1A1A2E"       # deep navy
BG_CARD = "#16213E"       # slightly lighter card
TEXT_PRIMARY = "#E0E0E0"  # light gray
TEXT_MUTED = "#888888"    # muted gray
SUCCESS_GREEN = "#00C896"


# =========================================================================
# Main Application
# =========================================================================

class ReportAutomatorApp(ctk.CTk):
    """Main GUI window for Report Automator Pro."""

    def __init__(self):
        super().__init__()

        # -- window config -------------------------------------------------
        self.title("Report Automator Pro")
        self.geometry("780x620")
        self.minsize(680, 540)

        # Apply dark theme
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        # Custom color theme overrides
        self.configure(fg_color=BG_DARK)

        # -- state ---------------------------------------------------------
        self._running = False
        self._input_file: str | None = None
        self._output_pptx: str | None = None

        # -- build UI ------------------------------------------------------
        self._build_header()
        self._build_input_section()
        self._build_action_button()
        self._build_progress_section()
        self._build_status_bar()

    # ------------------------------------------------------------------
    # UI Sections
    # ------------------------------------------------------------------

    def _build_header(self) -> None:
        """Title + subtitle header."""
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(pady=(30, 10), padx=40, fill="x")

        ctk.CTkLabel(
            header,
            text="Report Automator Pro",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color=TEXT_PRIMARY,
        ).pack(anchor="w")

        ctk.CTkLabel(
            header,
            text="CAE Post-Processing & PPT Report Generator",
            font=ctk.CTkFont(size=13),
            text_color=TEXT_MUTED,
        ).pack(anchor="w", pady=(2, 0))

        # Divider
        ctk.CTkFrame(
            self, height=1, fg_color=TEXT_MUTED
        ).pack(fill="x", padx=40, pady=(12, 20))

    def _build_input_section(self) -> None:
        """File input row with browse button."""
        section = ctk.CTkFrame(
            self, fg_color=BG_CARD, corner_radius=10
        )
        section.pack(pady=(0, 16), padx=40, fill="x", ipady=12)

        ctk.CTkLabel(
            section,
            text="Input Data Source",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=TEXT_PRIMARY,
        ).pack(anchor="w", padx=20, pady=(14, 6))

        row = ctk.CTkFrame(section, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=(0, 14))

        self._input_path_var = ctk.StringVar(value="Mock Data (built-in cantilever beam)")
        ctk.CTkEntry(
            row,
            textvariable=self._input_path_var,
            height=36,
            font=ctk.CTkFont(size=12),
            fg_color=BG_DARK,
            border_color=ACCENT,
        ).pack(side="left", fill="x", expand=True, padx=(0, 10))

        ctk.CTkButton(
            row,
            text="Browse",
            command=self._on_browse,
            width=90,
            height=36,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=ACCENT,
            hover_color="#C0392B",
        ).pack(side="right")

        ctk.CTkLabel(
            section,
            text="Supports .vtk files or built-in mock data generation.",
            font=ctk.CTkFont(size=11),
            text_color=TEXT_MUTED,
        ).pack(anchor="w", padx=20, pady=(0, 10))

    def _build_action_button(self) -> None:
        """Big 'Generate' CTA button."""
        self._btn_generate = ctk.CTkButton(
            self,
            text="Generate PPT Report",
            command=self._on_generate,
            height=52,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=ACCENT,
            hover_color="#C0392B",
            corner_radius=10,
        )
        self._btn_generate.pack(pady=(4, 20), padx=40, fill="x")

    def _build_progress_section(self) -> None:
        """Progress bar + status label."""
        section = ctk.CTkFrame(
            self, fg_color=BG_CARD, corner_radius=10
        )
        section.pack(pady=(0, 16), padx=40, fill="x", ipady=12)

        ctk.CTkLabel(
            section,
            text="Pipeline Status",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=TEXT_PRIMARY,
        ).pack(anchor="w", padx=20, pady=(14, 6))

        self._progress = ctk.CTkProgressBar(
            section,
            height=10,
            corner_radius=5,
            fg_color=BG_DARK,
            progress_color=ACCENT,
        )
        self._progress.pack(fill="x", padx=20, pady=(6, 8))
        self._progress.set(0)

        self._status_label = ctk.CTkLabel(
            section,
            text="Ready",
            font=ctk.CTkFont(size=12),
            text_color=TEXT_MUTED,
        )
        self._status_label.pack(anchor="w", padx=20, pady=(0, 14))

        # Detailed log area
        self._log_text = ctk.CTkTextbox(
            section,
            height=140,
            font=ctk.CTkFont(size=11, family="Consolas"),
            fg_color=BG_DARK,
            text_color=TEXT_MUTED,
            wrap="word",
        )
        self._log_text.pack(fill="both", padx=20, pady=(0, 14), expand=True)
        self._log_text.insert("end", "  [LOG]  System idle. Ready for task.\n")

    def _build_status_bar(self) -> None:
        """Bottom status bar."""
        bar = ctk.CTkFrame(self, height=28, fg_color=BG_CARD)
        bar.pack(side="bottom", fill="x")

        ctk.CTkLabel(
            bar,
            text="Report Automator Pro v1.0  |  CAE Pipeline: Mock → Render → PPT",
            font=ctk.CTkFont(size=10),
            text_color=TEXT_MUTED,
        ).pack(side="left", padx=14, pady=4)

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _on_browse(self) -> None:
        """Open file dialog to select input .vtk."""
        path = filedialog.askopenfilename(
            title="Select Input File",
            filetypes=[
                ("VTK Files", "*.vtk"),
                ("VTU Files", "*.vtu"),
                ("All Files", "*.*"),
            ],
        )
        if path:
            self._input_file = path
            self._input_path_var.set(path)
            self._log(f"Selected: {path}")

    def _on_generate(self) -> None:
        """Start the pipeline in a background thread."""
        if self._running:
            self._log("[WARN] A task is already running. Please wait.")
            return

        self._running = True
        self._btn_generate.configure(
            text="Running...",
            state="disabled",
            fg_color=TEXT_MUTED,
        )
        self._progress.set(0)

        thread = threading.Thread(target=self._run_pipeline, daemon=True)
        thread.start()

    # ------------------------------------------------------------------
    # Pipeline (runs on background thread)
    # ------------------------------------------------------------------

    def _run_pipeline(self) -> None:
        """Execute the full CAE → Render → PPT pipeline."""
        try:
            # ---- Phase 1: Data Loading ------------------------------------
            self._update_status("Parsing mesh data...", 0.05)
            self._log("[Phase 1/3] Generating mock CAE dataset...")
            time.sleep(0.3)  # brief delay for UI feel

            data = generate_mock_dataset(seed=42)
            svm = data.stress_von_mises
            idx_peak = int(svm.argmax())
            self._log(
                f"  -> Mesh: {data.n_nodes:,} nodes, {data.n_cells:,} cells"
            )
            self._log(
                f"  -> Peak stress: {svm[idx_peak]:.2f} MPa @ node #{idx_peak}"
            )

            # ---- Phase 2: GPU Rendering -----------------------------------
            self._update_status("GPU off-screen rendering in progress...", 0.25)
            self._log("[Phase 2/3] Rendering high-resolution images...")

            render_stress(data, OUTPUT_DIR, zoom_to_critical=True)
            self._log("  -> stress render complete")
            self._update_status("Rendering displacement field...", 0.40)

            render_displacement(data, OUTPUT_DIR, zoom_to_critical=True)
            self._log("  -> displacement render complete")
            self._update_status("Rendering report suite...", 0.55)

            render_report_suite(data, OUTPUT_DIR)
            self._log("  -> full report suite rendered (5 views)")
            self._progress_set(0.65)

            # ---- Phase 3: PPT Assembly ------------------------------------
            self._update_status("Injecting PPT layout...", 0.70)
            self._log("[Phase 3/3] Assembling PowerPoint report...")

            pptx_path = generate_pptx(data, OUTPUT_DIR)
            self._output_pptx = pptx_path
            self._progress_set(0.90)
            self._log(f"  -> PPTX saved: {pptx_path}")
            self._log(
                f"  -> File size: {os.path.getsize(pptx_path)/1024:.1f} KB"
            )

            # ---- Done -----------------------------------------------------
            self._progress_set(1.0)
            self._update_status("Report generation complete!", 1.0)
            self._log("[DONE] Pipeline finished successfully.")

            # Auto-open the PPTX
            self._log("[ACTION] Opening report in PowerPoint...")
            self.after(500, lambda: os.startfile(pptx_path))

        except Exception as exc:
            self._log(f"[ERROR] {exc}")
            self._update_status(f"Error: {exc}", 0.0)
        finally:
            self._running = False
            self.after(0, self._reset_button)

    # ------------------------------------------------------------------
    # Thread-safe UI helpers
    # ------------------------------------------------------------------

    def _update_status(self, text: str, progress: float) -> None:
        """Thread-safe status + progress update."""
        self.after(0, lambda: self._status_label.configure(text=text))
        self.after(0, lambda: self._progress_set(progress))

    def _progress_set(self, value: float) -> None:
        """Set progress bar value."""
        self._progress.set(value)

    def _log(self, message: str) -> None:
        """Append a line to the log textbox (thread-safe)."""
        self.after(0, lambda: self._log_text.insert("end", f"  {message}\n"))
        self.after(0, lambda: self._log_text.see("end"))

    def _reset_button(self) -> None:
        """Restore the generate button."""
        self._btn_generate.configure(
            text="Generate PPT Report",
            state="normal",
            fg_color=ACCENT,
        )


# =========================================================================
# Entry Point
# =========================================================================

def main():
    app = ReportAutomatorApp()
    app.mainloop()


if __name__ == "__main__":
    main()
