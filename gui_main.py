"""
Report Automator Pro — Desktop GUI
====================================
Modern dark-themed desktop application for one-click CAE report generation.
Supports English / Chinese bilingual toggle.

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

import tkinter as tk
import customtkinter as ctk
from customtkinter import filedialog
from tkinterdnd2 import DND_FILES
from tkinterdnd2.TkinterDnD import _require as _require_tkdnd

# -- app modules -----------------------------------------------------------
from src.mock_data import generate_mock_dataset
from src.renderer import render_stress, render_displacement, render_report_suite
from src.ppt_generator import generate_pptx
from src.odb_loader import run_odb_extraction, load_npz_to_mesh


# =========================================================================
# Globals
# =========================================================================

OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Brand colors for industrial dark theme
ACCENT = "#E94560"
ACCENT_HOVER = "#C0392B"
BG_DARK = "#1A1A2E"
BG_CARD = "#16213E"
TEXT_PRIMARY = "#E0E0E0"
TEXT_MUTED = "#888888"
SUCCESS_GREEN = "#00C896"
LANG_TOGGLE_BG = "#2A2A4A"


# =========================================================================
# i18n Dictionary
# =========================================================================

I18N = {
    "en": {
        "app.title": "Report Automator Pro",
        "app.subtitle": "CAE Post-Processing & PPT Report Generator",
        "input.label": "Input Data Source",
        "input.placeholder": "Mock Data (built-in cantilever beam)",
        "input.hint": "Supports .vtk files or built-in mock data generation.",
        "input.browse": "Browse",
        "input.dialog_title": "Select Input File",
        "btn.generate": "🚀  Generate PPT Report",
        "btn.running": "⏳  Running...",
        "progress.label": "Pipeline Status",
        "status.ready": "Ready",
        "status.parse": "Parsing mesh data...",
        "status.render_stress": "GPU off-screen rendering — stress field...",
        "status.render_disp": "GPU off-screen rendering — displacement field...",
        "status.render_suite": "Rendering multi-view report suite...",
        "status.ppt": "Injecting PPT layout & diagnostic text...",
        "status.done": "Report generation complete!",
        "status.error": "Error: {error}",
        "log.ready": "[LOG]  System idle. Ready for task.\n",
        "log.warn_running": "[WARN] A task is already running. Please wait.",
        "log.phase1": "[Phase 1/3] Generating mock CAE dataset...",
        "log.mesh": "  -> Mesh: {nodes:,} nodes, {cells:,} cells",
        "log.peak": "  -> Peak stress: {stress:.2f} MPa @ node #{idx}",
        "log.phase2": "[Phase 2/3] Rendering high-resolution images...",
        "log.stress_done": "  -> stress render complete",
        "log.disp_done": "  -> displacement render complete",
        "log.suite_done": "  -> full report suite rendered (5 views)",
        "log.phase3": "[Phase 3/3] Assembling PowerPoint report...",
        "log.pptx_saved": "  -> PPTX saved: {path}",
        "log.pptx_size": "  -> File size: {size:.1f} KB",
        "log.done": "[DONE] Pipeline finished successfully.",
        "log.open": "[ACTION] Opening report in PowerPoint...",
        "log.selected": "Selected: {path}",
        "drop.placeholder": "Drag & drop .odb / .npz / .vtk file here\n(or click Browse to select)",
        "drop.hover": "Release to load file",
        "log.odb_detected": "  -> Detected .odb file -- launching Abaqus extraction...",
        "log.odb_running": "  -> Running: abaqus python odb_bridge.py ...",
        "log.odb_done": "  -> Extraction complete: {path}",
        "log.odb_loaded": "  -> ODB data loaded into pipeline",
        "log.npz_loading": "  -> Loading pre-extracted data: {path}",
        "log.npz_loaded": "  -> NPZ data loaded into pipeline",
        "statusbar": "Report Automator Pro v1.0  |  CAE Pipeline: Mock → Render → PPT",
        "btn.lang": "中文",
        "lang.indicator": "EN",
    },
    "zh": {
        "app.title": "Report Automator Pro — 力学仿真自动化后处理",
        "app.subtitle": "有限元后处理 · 智能渲染 · PPT 报告一键生成",
        "input.label": "输入数据源",
        "input.placeholder": "内置 Mock 数据（悬臂梁模型）",
        "input.hint": "支持 .vtk / .vtu 文件，或使用内置 Mock 数据生成。",
        "input.browse": "浏览文件",
        "drop.placeholder": "拖拽 .odb / .npz / .vtk 文件到此处\n（或点击 [浏览文件] 选择）",
        "drop.hover": "松开鼠标以加载文件",
        "input.dialog_title": "选择输入文件",
        "btn.generate": "🚀  一键生成 PPT 报告",
        "btn.running": "⏳  正在运行...",
        "progress.label": "流水线状态",
        "status.ready": "就绪，等待指令",
        "status.parse": "正在解析网格数据...",
        "status.render_stress": "GPU 后台渲染中 — 应力场...",
        "status.render_disp": "GPU 后台渲染中 — 位移场...",
        "status.render_suite": "渲染多视角报告图集...",
        "status.ppt": "正在注入 PPT 版式与诊断文本...",
        "status.done": "报告生成完毕！",
        "status.error": "发生错误: {error}",
        "log.ready": "[就绪]  系统空闲，等待任务指令。\n",
        "log.warn_running": "[警告] 当前有任务正在运行，请等待完成。",
        "log.phase1": "[阶段 1/3] 正在生成 Mock CAE 数据集...",
        "log.mesh": "  -> 网格: {nodes:,} 节点, {cells:,} 单元",
        "log.peak": "  -> 峰值应力: {stress:.2f} MPa @ 节点 #{idx}",
        "log.phase2": "[阶段 2/3] 高清离屏渲染进行中...",
        "log.stress_done": "  -> 应力场渲染完成",
        "log.disp_done": "  -> 位移场渲染完成",
        "log.suite_done": "  -> 报告图集渲染完成 (5 张视图)",
        "log.phase3": "[阶段 3/3] 正在组装 PowerPoint 报告...",
        "log.pptx_saved": "  -> PPTX 已保存: {path}",
        "log.pptx_size": "  -> 文件大小: {size:.1f} KB",
        "log.done": "[完成] 全链路流水线执行成功。",
        "log.open": "[操作] 正在自动打开 PowerPoint 报告...",
        "log.selected": "已选择: {path}",
        "log.odb_detected": "  -> 检测到 .odb 文件 -- 启动 Abaqus 数据提取...",
        "log.odb_running": "  -> 执行: abaqus python odb_bridge.py ...",
        "log.odb_done": "  -> 提取完成: {path}",
        "log.odb_loaded": "  -> ODB 数据已加载至流水线",
        "log.npz_loading": "  -> 加载预提取数据: {path}",
        "log.npz_loaded": "  -> NPZ 数据已加载至流水线",
        "statusbar": "Report Automator Pro v1.0  |  流水线: Mock → 渲染 → PPT",
        "btn.lang": "English",
        "lang.indicator": "中文",
    },
}


# =========================================================================
# Main Application
# =========================================================================

class ReportAutomatorApp(ctk.CTk):
    """Main GUI window for Report Automator Pro — bilingual EN/ZH with drag-and-drop."""

    def __init__(self):
        super().__init__()

        # Load tkdnd Tcl package for drag-and-drop support
        try:
            _require_tkdnd(self)
        except (tk.TclError, Exception):
            pass  # tkdnd not available — drag-and-drop disabled

        # -- language state --------------------------------------------------
        self._lang = "en"

        # -- window config ---------------------------------------------------
        self.title("Report Automator Pro")
        self.geometry("780x650")
        self.minsize(680, 560)

        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")
        self.configure(fg_color=BG_DARK)

        # -- runtime state ---------------------------------------------------
        self._running = False
        self._input_file: str | None = None
        self._output_pptx: str | None = None

        # -- widget registry (for i18n refresh) ------------------------------
        self._widgets: dict[str, ctk.CTkBaseClass] = {}

        # -- build UI --------------------------------------------------------
        self._build_all()

    # ------------------------------------------------------------------
    # i18n helper
    # ------------------------------------------------------------------

    def _t(self, key: str, **kwargs) -> str:
        """Look up translated string.  Falls back to English."""
        text = I18N.get(self._lang, I18N["en"]).get(key, key)
        if kwargs:
            return text.format(**kwargs)
        return text

    def _set_lang(self, lang: str) -> None:
        """Switch language and refresh all UI text."""
        self._lang = lang
        self._refresh_ui()

    # ------------------------------------------------------------------
    # Full UI construction
    # ------------------------------------------------------------------

    def _build_all(self) -> None:
        self._build_header()
        self._build_input_section()
        self._build_action_button()
        self._build_progress_section()
        self._build_status_bar()

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(pady=(30, 10), padx=40, fill="x")

        # Title
        lbl = ctk.CTkLabel(
            header,
            text=self._t("app.title"),
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=TEXT_PRIMARY,
        )
        lbl.pack(anchor="w")
        self._widgets["title"] = lbl

        # Subtitle row with language toggle
        sub_row = ctk.CTkFrame(header, fg_color="transparent")
        sub_row.pack(fill="x", pady=(2, 0))

        lbl2 = ctk.CTkLabel(
            sub_row,
            text=self._t("app.subtitle"),
            font=ctk.CTkFont(size=13),
            text_color=TEXT_MUTED,
        )
        lbl2.pack(side="left")
        self._widgets["subtitle"] = lbl2

        # Language toggle button (top-right)
        self._lang_indicator = ctk.CTkLabel(
            sub_row,
            text="",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=ACCENT,
            width=40,
        )
        self._lang_indicator.pack(side="right", padx=(0, 8))

        btn_lang = ctk.CTkButton(
            sub_row,
            text=self._t("btn.lang"),
            command=self._on_toggle_lang,
            width=70,
            height=28,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=LANG_TOGGLE_BG,
            hover_color=ACCENT,
            corner_radius=6,
        )
        btn_lang.pack(side="right")
        self._widgets["btn_lang"] = btn_lang
        self._lang_indicator.configure(text=self._t("lang.indicator"))

        # Divider
        ctk.CTkFrame(self, height=1, fg_color=TEXT_MUTED).pack(
            fill="x", padx=40, pady=(12, 20)
        )

    # ------------------------------------------------------------------
    # Input section
    # ------------------------------------------------------------------

    def _build_input_section(self) -> None:
        section = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=10)
        section.pack(pady=(0, 16), padx=40, fill="x", ipady=12)

        lbl = ctk.CTkLabel(
            section,
            text=self._t("input.label"),
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=TEXT_PRIMARY,
        )
        lbl.pack(anchor="w", padx=20, pady=(14, 6))
        self._widgets["input_label"] = lbl

        # ---- Drag & Drop zone ----------------------------------------------
        self._drop_zone = tk.Frame(
            section,
            bg=BG_DARK,
            highlightbackground=ACCENT,
            highlightthickness=2,
            cursor="hand2",
        )
        self._drop_zone.pack(fill="x", padx=20, pady=(4, 8), ipady=22)

        # Register as DnD target
        self._drop_zone.drop_target_register(DND_FILES)
        self._drop_zone.dnd_bind("<<DragEnter>>", self._on_drop_enter)
        self._drop_zone.dnd_bind("<<DragLeave>>", self._on_drop_leave)
        self._drop_zone.dnd_bind("<<Drop>>", self._on_drop)

        self._drop_label = tk.Label(
            self._drop_zone,
            text=self._t("drop.placeholder"),
            font=("Segoe UI", 12),
            fg=TEXT_MUTED,
            bg=BG_DARK,
            justify="center",
        )
        self._drop_label.pack(expand=True)
        self._widgets["drop_label"] = self._drop_label

        # ---- File path row -------------------------------------------------
        row = ctk.CTkFrame(section, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=(0, 14))

        self._input_path_var = ctk.StringVar(value=self._t("input.placeholder"))
        ctk.CTkEntry(
            row,
            textvariable=self._input_path_var,
            height=36,
            font=ctk.CTkFont(size=12),
            fg_color=BG_DARK,
            border_color=ACCENT,
        ).pack(side="left", fill="x", expand=True, padx=(0, 10))

        btn = ctk.CTkButton(
            row,
            text=self._t("input.browse"),
            command=self._on_browse,
            width=90,
            height=36,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
        )
        btn.pack(side="right")
        self._widgets["btn_browse"] = btn

        hint = ctk.CTkLabel(
            section,
            text=self._t("input.hint"),
            font=ctk.CTkFont(size=11),
            text_color=TEXT_MUTED,
        )
        hint.pack(anchor="w", padx=20, pady=(0, 10))
        self._widgets["input_hint"] = hint

    # ------------------------------------------------------------------
    # Action button
    # ------------------------------------------------------------------

    def _build_action_button(self) -> None:
        self._btn_generate = ctk.CTkButton(
            self,
            text=self._t("btn.generate"),
            command=self._on_generate,
            height=52,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            corner_radius=10,
        )
        self._btn_generate.pack(pady=(4, 20), padx=40, fill="x")

    # ------------------------------------------------------------------
    # Progress section
    # ------------------------------------------------------------------

    def _build_progress_section(self) -> None:
        section = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=10)
        section.pack(pady=(0, 16), padx=40, fill="both", expand=True, ipady=12)

        lbl = ctk.CTkLabel(
            section,
            text=self._t("progress.label"),
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=TEXT_PRIMARY,
        )
        lbl.pack(anchor="w", padx=20, pady=(14, 6))
        self._widgets["progress_label"] = lbl

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
            text=self._t("status.ready"),
            font=ctk.CTkFont(size=12),
            text_color=TEXT_MUTED,
        )
        self._status_label.pack(anchor="w", padx=20, pady=(0, 14))

        # Log area
        self._log_text = ctk.CTkTextbox(
            section,
            height=140,
            font=ctk.CTkFont(size=11, family="Consolas"),
            fg_color=BG_DARK,
            text_color=TEXT_MUTED,
            wrap="word",
        )
        self._log_text.pack(fill="both", padx=20, pady=(0, 14), expand=True)
        self._log_text.insert("end", self._t("log.ready"))

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------

    def _build_status_bar(self) -> None:
        bar = ctk.CTkFrame(self, height=28, fg_color=BG_CARD)
        bar.pack(side="bottom", fill="x")

        lbl = ctk.CTkLabel(
            bar,
            text=self._t("statusbar"),
            font=ctk.CTkFont(size=10),
            text_color=TEXT_MUTED,
        )
        lbl.pack(side="left", padx=14, pady=4)
        self._widgets["statusbar"] = lbl

    # ------------------------------------------------------------------
    # i18n refresh — update all dynamic text
    # ------------------------------------------------------------------

    def _refresh_ui(self) -> None:
        """Re-apply all translatable strings to widgets."""
        self._widgets["title"].configure(text=self._t("app.title"))
        self._widgets["subtitle"].configure(text=self._t("app.subtitle"))
        self._widgets["input_label"].configure(text=self._t("input.label"))
        self._widgets["input_hint"].configure(text=self._t("input.hint"))
        self._widgets["btn_browse"].configure(text=self._t("input.browse"))
        self._widgets["btn_lang"].configure(text=self._t("btn.lang"))
        self._widgets["progress_label"].configure(text=self._t("progress.label"))
        self._widgets["statusbar"].configure(text=self._t("statusbar"))
        self._lang_indicator.configure(text=self._t("lang.indicator"))

        # Input placeholder
        if not self._input_file:
            self._input_path_var.set(self._t("input.placeholder"))
            self._drop_label.configure(
                fg=TEXT_MUTED,
                text=self._t("drop.placeholder"),
            )

        # Status label
        if not self._running:
            self._status_label.configure(text=self._t("status.ready"))

        # Generate button
        if not self._running:
            self._btn_generate.configure(text=self._t("btn.generate"))

    # ------------------------------------------------------------------
    # Language toggle
    # ------------------------------------------------------------------

    def _on_toggle_lang(self) -> None:
        new_lang = "zh" if self._lang == "en" else "en"
        self._set_lang(new_lang)
        self._log(self._t("log.ready").strip())

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _on_browse(self) -> None:
        path = filedialog.askopenfilename(
            title=self._t("input.dialog_title"),
            filetypes=[
                ("ABAQUS ODB", "*.odb"),
                ("VTK Files", "*.vtk"),
                ("VTU Files", "*.vtu"),
                ("NPZ (pre-extracted)", "*.npz"),
                ("All Files", "*.*"),
            ],
        )
        if path:
            self._set_input_file(path)

    # ------------------------------------------------------------------
    # Drag & Drop handlers
    # ------------------------------------------------------------------

    def _on_drop_enter(self, event) -> None:
        self._drop_zone.configure(highlightbackground=SUCCESS_GREEN, highlightthickness=3)
        self._drop_label.configure(fg=SUCCESS_GREEN, text=self._t("drop.hover"))

    def _on_drop_leave(self, event) -> None:
        self._drop_zone.configure(highlightbackground=ACCENT, highlightthickness=2)
        self._drop_label.configure(fg=TEXT_MUTED, text=self._t("drop.placeholder"))

    def _on_drop(self, event) -> None:
        """Handle file drop — extract the first valid file path."""
        self._on_drop_leave(event)  # reset visuals

        # tkinterdnd2 wraps paths in {} on Windows; strip them
        raw = event.data.strip()
        if raw.startswith("{") and raw.endswith("}"):
            raw = raw[1:-1]

        # Handle multi-file drop: take the first valid CAE file
        paths = [p.strip() for p in raw.split("} {") if p.strip()]
        valid_exts = (".odb", ".npz", ".vtk", ".vtu")
        for p in paths:
            pl = p.lower()
            if any(pl.endswith(ext) for ext in valid_exts):
                self._set_input_file(p)
                return

        # If no recognized extension, take the first file anyway
        if paths:
            self._set_input_file(paths[0])

    def _set_input_file(self, path: str) -> None:
        """Update UI state when a file is selected (by browse or drop)."""
        self._input_file = path
        self._input_path_var.set(path)
        self._log(self._t("log.selected", path=path))
        # Show filename + type badge in drop zone
        ext = os.path.splitext(path)[1].upper().replace(".", "")
        self._drop_label.configure(
            fg=SUCCESS_GREEN,
            text=f"[{ext}]  {os.path.basename(path)}",
        )

    def _on_generate(self) -> None:
        if self._running:
            self._log(self._t("log.warn_running"))
            return

        self._running = True
        self._btn_generate.configure(
            text=self._t("btn.running"),
            state="disabled",
            fg_color=TEXT_MUTED,
        )
        self._progress.set(0)

        thread = threading.Thread(target=self._run_pipeline, daemon=True)
        thread.start()

    # ------------------------------------------------------------------
    # Pipeline (background thread)
    # ------------------------------------------------------------------

    def _run_pipeline(self) -> None:
        lang = self._lang  # capture current language for thread
        try:
            # Phase 1: Data
            self._update_status(self._t("status.parse"), 0.05)
            self._log(self._t("log.phase1"))

            input_path = self._input_file
            if input_path and input_path.lower().endswith(".odb"):
                # ----- ABAQUS .odb -> extraction via Abaqus Python ----------
                self._log(self._t("log.odb_detected"))
                npz_path = input_path.replace(".odb", "_extracted.npz")
                self._log(self._t("log.odb_running"))
                self._progress_set(0.08)
                run_odb_extraction(input_path, npz_path)
                self._log(self._t("log.odb_done", path=npz_path))
                self._progress_set(0.15)
                data = load_npz_to_mesh(npz_path)
                self._log(self._t("log.odb_loaded"))
            elif input_path and input_path.lower().endswith(".npz"):
                # ----- Pre-extracted .npz -----------------------------------
                self._log(self._t("log.npz_loading", path=input_path))
                data = load_npz_to_mesh(input_path)
                self._log(self._t("log.npz_loaded"))
            else:
                # ----- Mock data (built-in) ---------------------------------
                time.sleep(0.3)
                data = generate_mock_dataset(seed=42)

            svm = data.stress_von_mises
            idx_peak = int(svm.argmax())
            self._log(self._t("log.mesh", nodes=data.n_nodes, cells=data.n_cells))
            self._log(self._t("log.peak", stress=svm[idx_peak], idx=idx_peak))

            # Phase 2: Render
            self._update_status(self._t("status.render_stress"), 0.25)
            self._log(self._t("log.phase2"))
            render_stress(data, OUTPUT_DIR, zoom_to_critical=True)
            self._log(self._t("log.stress_done"))

            self._update_status(self._t("status.render_disp"), 0.40)
            render_displacement(data, OUTPUT_DIR, zoom_to_critical=True)
            self._log(self._t("log.disp_done"))

            self._update_status(self._t("status.render_suite"), 0.55)
            render_report_suite(data, OUTPUT_DIR)
            self._log(self._t("log.suite_done"))
            self._progress_set(0.65)

            # Phase 3: PPT
            self._update_status(self._t("status.ppt"), 0.70)
            self._log(self._t("log.phase3"))

            pptx_path = generate_pptx(data, OUTPUT_DIR)
            self._output_pptx = pptx_path
            self._progress_set(0.90)
            self._log(self._t("log.pptx_saved", path=pptx_path))
            self._log(self._t("log.pptx_size",
                size=os.path.getsize(pptx_path) / 1024))

            # Done
            self._progress_set(1.0)
            self._update_status(self._t("status.done"), 1.0)
            self._log(self._t("log.done"))
            self._log(self._t("log.open"))
            self.after(500, lambda: os.startfile(pptx_path))

        except Exception as exc:
            self._log(f"[ERROR] {exc}")
            self._update_status(self._t("status.error", error=str(exc)), 0.0)
        finally:
            self._running = False
            self.after(0, self._reset_button)

    # ------------------------------------------------------------------
    # Thread-safe UI helpers
    # ------------------------------------------------------------------

    def _update_status(self, text: str, progress: float) -> None:
        self.after(0, lambda: self._status_label.configure(text=text))
        self.after(0, lambda: self._progress_set(progress))

    def _progress_set(self, value: float) -> None:
        self._progress.set(value)

    def _log(self, message: str) -> None:
        self.after(0, lambda: self._log_text.insert("end", f"  {message}\n"))
        self.after(0, lambda: self._log_text.see("end"))

    def _reset_button(self) -> None:
        self._btn_generate.configure(
            text=self._t("btn.generate"),
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
