"""
app_ui.py
App desktop con 3 tab per visualizzare le tabelle del foglio 2026.
"""

import math
import os
import sys
import threading
import tkinter as tk
from datetime import datetime, date, timedelta
from tkinter import ttk, messagebox

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from auth import get_dropbox_client
from parser_2026 import (get_tables, get_fixed_platform_goals, get_gt_anno_data,
                         get_bondo_evo_daily_values, get_gpp_anno_data,
                         get_total_monthly_comparison_data, get_monthly_comparison_total,
                         get_monthly_comparison_chart_points,
                         get_bondo_evo_selectable_targets,
                          get_bondo_evo_next_unreached_target,
                          get_bondo_evo_days_completion,
                         get_euro_milestone_targets,
                         get_progressive_amount_targets,
                         get_yearly_main_tables_data, get_fin_inv_debts,
                         detect_current_year_sheet, invalidate_cache, MESI,
                         MONTHLY_COMPARISON_SCOPES)
from numbers import Real

# ── Palette colori ──────────────────────────────────────────────
BG         = "#1e1e2e"
BG_FRAME   = "#2a2a3e"
BG_TABLE   = "#2a2a3e"
FG         = "#cdd6f4"
FG_HEADER  = "#89b4fa"
FG_SOMMA   = "#a6e3a1"
FG_ACCENT  = "#f38ba8"
FG_PERCENT = "#1e3a8a"  # Blu scuro per testo percentuale nel grafico
FG_RESIDUO = "#ef4444"  # Rosso per la parte residua del grafico
FG_NEGATIVE = "#f87171"
SEL_BG     = "#45475a"
FONT_TITLE = ("Segoe UI", 13, "bold")
FONT_TAB   = ("Segoe UI", 10, "bold")
FONT_TABLE = ("Segoe UI", 10)
FONT_SMALL = ("Segoe UI", 9)

# Dimensioni grafico: leggermente ridotte per stare meglio su finestre piccole
GRAPH_CANVAS_W = 300
GRAPH_CANVAS_H = 300
PIE_MARGIN = 18
PIE_MIN_DIAMETER = 170
PIE_MAX_DIAMETER = 220

TAB_LABELS = {
    "investimenti": "💰  Investimenti",
    "guadagni":     "📈  Guadagni",
    "inv_guad":     "📊  Inv + Guad",
    "grafici":      "📉  Grafici",
    "statistiche_progressive": "🧮  Statistiche progressive",
    "bondora_evolution": "🧬  Bondora Evolution",
    "investimenti_attuali_vivi": "💵  Now Alive",
    "next_to_be":   "🎯  Next to be",
    "fin_inv":      "🧾  Fin - Inv",
}

MAIN_TABLE_KEYS = ("investimenti", "guadagni", "inv_guad")

GIORNI_SETTIMANA_IT = [
    "Lunedi",
    "Martedi",
    "Mercoledi",
    "Giovedi",
    "Venerdi",
    "Sabato",
    "Domenica",
]


def _resource_path(relative_path: str) -> str:
    """Restituisce il path risolto sia in dev che dentro bundle PyInstaller."""
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


class App(tk.Tk):
    def __init__(self):
        super().__init__(className="OwnFinance")
        self._icon_image = None
        self._set_window_icon()
        self.title("Own Finance – 2026")
        self.configure(bg=BG)
        self.resizable(True, True)
        # Apri a schermo intero (compatibile Linux/Windows/macOS)
        self.after(50, self._maximize_window)

        self.graph_platform_var = tk.StringVar()
        self.graph_month_var = tk.StringVar()
        self.current_year_sheet: str = str(datetime.now().year)  # verrà aggiornato al caricamento
        self.graph_platform_cb: ttk.Combobox | None = None
        self.graph_month_cb: ttk.Combobox | None = None
        self.graph_canvas: tk.Canvas | None = None
        self.graph_info_var = tk.StringVar(value="Carico dati grafico...")
        self.graph_empty_var = tk.StringVar(value="In attesa dei dati...")
        self.table_views: dict[str, dict[str, tk.Widget]] = {}
        self.tables: dict = {}
        self.tables_by_year: dict[str, dict] = {}
        self.main_tab_years: list[str] = []
        self.main_year_var = tk.StringVar()
        self.main_year_cbs: dict[str, ttk.Combobox] = {}
        self.platform_goals: dict[str, float] = {}

        self.gt_year_var = tk.StringVar()
        self.gt_platform_var = tk.StringVar()
        self.gt_metric_label_var = tk.StringVar()
        self.gt_year_cb: ttk.Combobox | None = None
        self.gt_platform_cb: ttk.Combobox | None = None
        self.gt_metric_cb: ttk.Combobox | None = None
        self.gt_result_var = tk.StringVar(value="Seleziona i filtri per visualizzare il valore.")
        self.gt_hint_var = tk.StringVar(value="")
        self.gt_data: dict[str, object] = {}
        self.gt_window: tk.Toplevel | None = None
        self.gt_chart_frame: tk.Frame | None = None
        self.gt_mpl_canvas: FigureCanvasTkAgg | None = None
        self.gt_compare_frame: tk.Frame | None = None
        self.gt_compare_tree: ttk.Treeview | None = None

        self.bondo_evo_daily_var = tk.StringVar()
        self.bondo_evo_daily_cb: ttk.Combobox | None = None
        self.bondo_evo_data: dict[float, dict[str, object]] = {}
        self.bondo_evo_graph_canvas: tk.Canvas | None = None
        self.bondo_evo_next_graph_canvas: tk.Canvas | None = None
        self.bondo_evo_info_frame: tk.Frame | None = None
        self.bondo_evo_info_frame: tk.Frame | None = None
        self.bondo_evo_next_info_var = tk.StringVar(value="Prossimo obiettivo: in attesa dati")
        self._bondo_evo_redraw_job: str | None = None

        # Confronto mensile (GPP_ANNO)
        self.gpp_data: dict[str, object] = {}
        self.gpp_window: tk.Toplevel | None = None
        self.gpp_month_var = tk.StringVar()
        self.gpp_platform_var = tk.StringVar()
        self.gpp_month_cb: ttk.Combobox | None = None
        self.gpp_platform_cb: ttk.Combobox | None = None
        self.gpp_compare_tree: ttk.Treeview | None = None
        self.gpp_chart_frame: tk.Frame | None = None
        self.gpp_mpl_canvas: FigureCanvasTkAgg | None = None

        # Confronto totale mensile (storico + anno corrente)
        self.ctm_data: dict[str, object] = {}
        self.ctm_window: tk.Toplevel | None = None
        self.ctm_scope_var = tk.StringVar()
        self.ctm_scope_cb: ttk.Combobox | None = None
        self.ctm_hint_var = tk.StringVar(value="")
        self.ctm_table_canvas: tk.Canvas | None = None
        self.ctm_table_body: tk.Frame | None = None
        self.ctm_tooltip: tk.Toplevel | None = None
        self.ctm_tooltip_label: tk.Label | None = None
        self.ctm_graph_window: tk.Toplevel | None = None
        self.ctm_graph_frame: tk.Frame | None = None
        self.ctm_graph_year_var = tk.StringVar()
        self.ctm_graph_year_cb: ttk.Combobox | None = None
        self.ctm_graph_title_var = tk.StringVar(value="")
        self.ctm_graph_hint_var = tk.StringVar(value="")
        self.ctm_graph_mpl_canvas: FigureCanvasTkAgg | None = None

        # Medie mensili
        self.mm_window: tk.Toplevel | None = None
        self.mm_month_var = tk.StringVar()
        self.mm_platform_var = tk.StringVar()
        self.mm_year_var = tk.StringVar()
        self.mm_month_cb: ttk.Combobox | None = None
        self.mm_platform_cb: ttk.Combobox | None = None
        self.mm_year_cb: ttk.Combobox | None = None
        self.mm_title_var = tk.StringVar(value="")
        self.mm_result_var = tk.StringVar(value="Seleziona i filtri per visualizzare il valore.")
        self.mm_chart_frame: tk.Frame | None = None
        self.mm_mpl_canvas: FigureCanvasTkAgg | None = None

        # Previsionale
        self.pv_window: tk.Toplevel | None = None
        self.pv_platform_var = tk.StringVar()
        self.pv_step_var = tk.StringVar()
        self.pv_platform_cb: ttk.Combobox | None = None
        self.pv_step_label: tk.Label | None = None
        self.pv_step_cb: ttk.Combobox | None = None
        self.pv_targets_frame: tk.Frame | None = None
        self.pv_title_var = tk.StringVar(value="")
        self.pv_result_var = tk.StringVar(value="Seleziona una piattaforma per calcolare il previsionale.")
        self.pv_hint_var = tk.StringVar(value="")
        self.pv_active_detail_index: int | None = None

        # Previsionale mensile Bondora
        self.bmb_window: tk.Toplevel | None = None
        self.bmb_hint_var = tk.StringVar(value="")
        self.bmb_table_canvas: tk.Canvas | None = None
        self.bmb_table_body: tk.Frame | None = None
        self.bmb_detail_window: tk.Toplevel | None = None
        self.bmb_monthly_data: dict[tuple[int, int], dict[str, object]] = {}

        # Previsionale Bondora con aggiunta
        self.pbca_window: tk.Toplevel | None = None
        self.pbca_selected_date_var = tk.StringVar(value="")
        self.pbca_amount_var = tk.StringVar(value="")
        self.pbca_hint_var = tk.StringVar(value="Seleziona data e importo, quindi premi 'Calcola'.")
        self.pbca_table_canvas: tk.Canvas | None = None
        self.pbca_table_body: tk.Frame | None = None
        self.pbca_monthly_data: dict[tuple[int, int], dict[str, object]] = {}
        self.pbca_detail_window: tk.Toplevel | None = None

        # Interesse composto Bondora
        self.icb_window: tk.Toplevel | None = None
        self.icb_hint_var = tk.StringVar(value="")
        self.icb_table_canvas: tk.Canvas | None = None
        self.icb_table_body: tk.Frame | None = None
        self.icb_yearly_data: dict[int, float] = {}

        self.live_bm_value_var = tk.StringVar(value="EUR --")
        self.live_bmr_value_var = tk.StringVar(value="EUR --")
        self.live_bondora_value_var = tk.StringVar(value="EUR --")
        self.live_mintos_value_var = tk.StringVar(value="EUR --")
        self.live_relender_value_var = tk.StringVar(value="EUR --")

        # Next to be tab
        self.ntb_mode_var = tk.StringVar(value="Previsionale")
        self.ntb_amount_var = tk.StringVar(value="0")
        self.ntb_evo_daily_var = tk.StringVar()
        self.ntb_evo_daily_cb: ttk.Combobox | None = None
        self.ntb_content_frame: tk.Frame | None = None
        self.ntb_evo_graph_canvas: tk.Canvas | None = None
        self.ntb_evo_info_frame: tk.Frame | None = None
        self._ntb_virtual_evo_data: dict = {}

        # Main tab charts window (Investimenti / Guadagni / Inv+Guad)
        self.mtc_window: tk.Toplevel | None = None
        self.mtc_table_key: str = ""
        self.mtc_year_var = tk.StringVar()
        self.mtc_platform_var = tk.StringVar()
        self.mtc_chart_frame: tk.Frame | None = None
        self.mtc_mpl_canvas: FigureCanvasTkAgg | None = None
        self.mtc_year_cb: ttk.Combobox | None = None
        self.mtc_platform_cb: ttk.Combobox | None = None

        # Fin - Inv tab
        self.fin_inv_type_var = tk.StringVar(value="Fhome + Fcar")
        self.fin_inv_scope_var = tk.StringVar(value="Ready To Redeem")
        self.fin_inv_directa_input_var = tk.StringVar(value="0")
        self.fin_inv_debts: dict[str, float] = {"fin_home": 0.0, "fin_car": 0.0, "total": 0.0}
        self.fin_inv_debt_value_var = tk.StringVar(value="EUR --")
        self.fin_inv_diff_value_var = tk.StringVar(value="EUR --")
        self.fin_inv_total_inv_title_var = tk.StringVar(value="Totale investimenti (Ready To Redeem)")
        self.fin_inv_total_inv_value_var = tk.StringVar(value="EUR --")
        self.fin_inv_bondora_var = tk.StringVar(value="Bondora: EUR --")
        self.fin_inv_mintos_var = tk.StringVar(value="Mintos: EUR --")
        self.fin_inv_relender_var = tk.StringVar(value="ReLender: EUR --")
        self.fin_inv_directa_var = tk.StringVar(value="Directa: EUR --")
        self.fin_inv_diff_label: tk.Label | None = None

        self._build_header()
        self._build_notebook()
        self._build_statusbar()

        # carica i dati in background per non bloccare la UI
        threading.Thread(target=self._load_data, daemon=True).start()

    # ── Layout ──────────────────────────────────────────────────

    # ── Utilità finestra ────────────────────────────────────────

    def _maximize_window(self):
        """Apre l'app a schermo intero in modo cross-platform."""
        try:
            # Linux / GNOME (extended window manager)
            self.attributes("-zoomed", True)
        except tk.TclError:
            pass
        try:
            # Windows
            self.state("zoomed")
        except tk.TclError:
            pass

    def _refocus_main(self):
        """Riporta la finestra principale in primo piano."""
        self.deiconify()
        self.lift()
        self.focus_force()

    def _build_header(self):
        hdr = tk.Frame(self, bg=BG, pady=10)
        hdr.pack(fill="x", padx=20)
        self.lbl_header = tk.Label(hdr, text=f"Own Finance  —  Riepilogo {self.current_year_sheet}",
                 font=FONT_TITLE, bg=BG, fg=FG_HEADER)
        self.lbl_header.pack(side="left")
        
        # Pulsante Aggiorna con stile dei tab
        btn_refresh = tk.Button(
            hdr,
            text="🔄 Aggiorna",
            font=FONT_TAB,
            fg=FG,
            bg=BG_FRAME,
            activeforeground=FG_HEADER,
            activebackground=SEL_BG,
            relief="flat",
            bd=0,
            padx=14,
            pady=6,
            cursor="hand2",
            command=self._refresh_all_data,
        )
        btn_refresh.pack(side="right", padx=(0, 10))
        
        self.lbl_update = tk.Label(hdr, text="Caricamento dati…",
                                   font=FONT_SMALL, bg=BG, fg=FG)
        self.lbl_update.pack(side="right")

    def _build_notebook(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TNotebook",          background=BG,       borderwidth=0)
        style.configure("TNotebook.Tab",      background=BG_FRAME, foreground=FG,
                        font=FONT_TAB,        padding=[14, 6])
        style.map("TNotebook.Tab",
                  background=[("selected", BG_TABLE)],
                  foreground=[("selected", FG_HEADER)])
        style.configure("Treeview",           background=BG_TABLE, foreground=FG,
                        fieldbackground=BG_TABLE, font=FONT_TABLE,
                        rowheight=28,         borderwidth=0)
        style.configure("Treeview.Heading",   background=BG_FRAME, foreground=FG_HEADER,
                        font=FONT_TAB)
        style.map("Treeview", background=[("selected", SEL_BG)])

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=(0, 5))
        self.notebook.bind("<<NotebookTabChanged>>", self._on_notebook_tab_changed)

        self.table_views: dict[str, dict[str, tk.Widget]] = {}
        self.tab_frames: dict[str, tk.Frame] = {}
        for key, label in TAB_LABELS.items():
            frame = tk.Frame(self.notebook, bg=BG_TABLE)
            self.tab_frames[key] = frame
            self.notebook.add(frame, text=label)

            if key == "grafici":
                self._build_graphs_placeholder(frame)
            elif key == "statistiche_progressive":
                self._build_progressive_tab(frame)
            elif key == "bondora_evolution":
                self._build_bondora_evolution_tab(frame)
            elif key == "investimenti_attuali_vivi":
                self._build_live_investments_tab(frame)
            elif key == "next_to_be":
                self._build_next_to_be_tab(frame)
            elif key == "fin_inv":
                self._build_fin_inv_tab(frame)
            else:
                self.table_views[key] = self._build_data_table(frame, key)

    def _build_fin_inv_tab(self, parent: tk.Frame):
        wrapper = tk.Frame(parent, bg=BG_TABLE)
        wrapper.pack(fill="both", expand=True, padx=16, pady=16)

        tk.Label(
            wrapper,
            text="Fin - Inv",
            font=("Segoe UI", 12, "bold"),
            bg=BG_TABLE,
            fg=FG_HEADER,
        ).pack(anchor="w")

        controls = tk.Frame(wrapper, bg=BG_TABLE)
        controls.pack(fill="x", pady=(12, 0))

        tk.Label(
            controls,
            text="Categoria",
            font=FONT_SMALL,
            bg=BG_TABLE,
            fg=FG_HEADER,
        ).pack(side="left")
        ttk.Combobox(
            controls,
            textvariable=self.fin_inv_type_var,
            state="readonly",
            width=18,
            values=["Fin casa", "Fin car", "Fhome + Fcar"],
        ).pack(side="left", padx=(8, 20))

        tk.Label(
            controls,
            text="Vista",
            font=FONT_SMALL,
            bg=BG_TABLE,
            fg=FG_HEADER,
        ).pack(side="left")
        ttk.Combobox(
            controls,
            textvariable=self.fin_inv_scope_var,
            state="readonly",
            width=18,
            values=["Ready To Redeem", "All", "Only Directa"],
        ).pack(side="left", padx=(8, 0))

        controls2 = tk.Frame(wrapper, bg=BG_TABLE)
        controls2.pack(fill="x", pady=(10, 0))

        tk.Label(
            controls2,
            text="Directa extra (€)",
            font=FONT_SMALL,
            bg=BG_TABLE,
            fg=FG_HEADER,
        ).pack(side="left")
        directa_entry = tk.Entry(
            controls2,
            textvariable=self.fin_inv_directa_input_var,
            width=14,
            bg=BG_FRAME,
            fg=FG,
            insertbackground=FG,
            relief="flat",
            font=FONT_TABLE,
        )
        directa_entry.pack(side="left", padx=(8, 10))

        tk.Label(
            controls2,
            text="(netto: 74% dell'importo inserito)",
            font=FONT_SMALL,
            bg=BG_TABLE,
            fg=FG,
        ).pack(side="left")

        self.fin_inv_type_var.trace_add("write", lambda *_: self._refresh_fin_inv_tab())
        self.fin_inv_scope_var.trace_add("write", lambda *_: self._refresh_fin_inv_tab())
        self.fin_inv_directa_input_var.trace_add("write", lambda *_: self._refresh_fin_inv_tab())
        directa_entry.bind("<Return>", lambda _e: self._refresh_fin_inv_tab())

        body = tk.Frame(wrapper, bg=BG_TABLE)
        body.pack(fill="both", expand=True, pady=(14, 0))

        left = tk.Frame(body, bg=BG_FRAME, padx=16, pady=14)
        left.pack(side="left", fill="both", expand=True)

        tk.Label(left, text="Debito selezionato", font=FONT_TAB, bg=BG_FRAME, fg=FG_HEADER).pack(anchor="w")
        tk.Label(
            left,
            textvariable=self.fin_inv_debt_value_var,
            font=("Segoe UI", 18, "bold"),
            bg=BG_FRAME,
            fg=FG_NEGATIVE,
        ).pack(anchor="w", pady=(6, 8))

        tk.Label(
            left,
            textvariable=self.fin_inv_total_inv_title_var,
            font=FONT_TAB,
            bg=BG_FRAME,
            fg=FG_HEADER,
        ).pack(anchor="w", pady=(6, 0))
        tk.Label(
            left,
            textvariable=self.fin_inv_total_inv_value_var,
            font=("Segoe UI", 18, "bold"),
            bg=BG_FRAME,
            fg=FG_SOMMA,
        ).pack(anchor="w", pady=(4, 0))
        tk.Label(
            left,
            text="Differenza (Debiti - Investimenti)",
            font=FONT_TAB,
            bg=BG_FRAME,
            fg=FG_HEADER,
        ).pack(anchor="w", pady=(10, 0))
        self.fin_inv_diff_label = tk.Label(
            left,
            textvariable=self.fin_inv_diff_value_var,
            font=("Segoe UI", 18, "bold"),
            bg=BG_FRAME,
            fg=FG_NEGATIVE,
        )
        self.fin_inv_diff_label.pack(anchor="w", pady=(4, 0))

        right = tk.Frame(body, bg=BG_FRAME, padx=16, pady=14)
        right.pack(side="left", fill="y", padx=(12, 0))

        tk.Label(right, text="Dettaglio investimenti", font=FONT_TAB, bg=BG_FRAME, fg=FG_HEADER).pack(anchor="w", pady=(0, 6))
        tk.Label(right, textvariable=self.fin_inv_bondora_var, font=FONT_SMALL, bg=BG_FRAME, fg=FG).pack(anchor="w")
        tk.Label(right, textvariable=self.fin_inv_mintos_var, font=FONT_SMALL, bg=BG_FRAME, fg=FG).pack(anchor="w", pady=(2, 0))
        tk.Label(right, textvariable=self.fin_inv_relender_var, font=FONT_SMALL, bg=BG_FRAME, fg=FG).pack(anchor="w", pady=(2, 0))
        tk.Label(right, textvariable=self.fin_inv_directa_var, font=FONT_SMALL, bg=BG_FRAME, fg=FG).pack(anchor="w", pady=(2, 0))

    def _get_fin_inv_debt_total(self) -> float:
        selection = self.fin_inv_type_var.get().strip()
        fin_home = float(self.fin_inv_debts.get("fin_home", 0.0) or 0.0)
        fin_car = float(self.fin_inv_debts.get("fin_car", 0.0) or 0.0)

        if selection == "Fin casa":
            return fin_home
        if selection == "Fin car":
            return fin_car
        return fin_home + fin_car

    def _refresh_fin_inv_tab(self):
        if not hasattr(self, "fin_inv_debt_value_var"):
            return

        debt_total = self._get_fin_inv_debt_total()
        self.fin_inv_debt_value_var.set(self._format_money_it(debt_total))

        bondora = self._get_current_platform_amount("Bondora")
        mintos = self._get_current_platform_amount("Mintos")
        relender = self._get_current_platform_amount("ReLender", aliases=["Re Lender", "Re-Lender", "Relender"])

        directa_extra_raw = self._parse_localized_number(self.fin_inv_directa_input_var.get())
        directa_extra = float(directa_extra_raw or 0.0)
        directa_total = 5900.0 + (directa_extra * 0.74)

        scope = self.fin_inv_scope_var.get().strip()
        
        # Calcola gli investimenti in base alla vista selezionata
        if scope == "Only Directa":
            # Solo Directa, senza Bondora, Mintos, ReLender
            investments_total = directa_total
        elif scope == "All":
            # Ready To Redeem + ReLender
            investments_total = bondora + mintos + directa_total + relender
        else:  # "Ready To Redeem" (default)
            # Ready To Redeem senza ReLender
            investments_total = bondora + mintos + directa_total

        self.fin_inv_bondora_var.set(f"Bondora: {self._format_money_it(bondora)}")
        self.fin_inv_mintos_var.set(f"Mintos: {self._format_money_it(mintos)}")
        rel_text = f"ReLender: {self._format_money_it(relender)}"
        if scope == "Only Directa":
            rel_text += " (escluso in Only Directa)"
        elif scope == "Ready To Redeem":
            rel_text += " (escluso in Ready To Redeem)"
        self.fin_inv_relender_var.set(rel_text)
        self.fin_inv_directa_var.set(
            f"Directa: {self._format_money_it(directa_total)} (5.900,00 + 74% input)"
        )
        self.fin_inv_total_inv_title_var.set(f"Totale investimenti ({scope})")
        self.fin_inv_total_inv_value_var.set(self._format_money_it(investments_total))

        diff = debt_total - investments_total
        if diff > 0:
            self.fin_inv_diff_value_var.set(self._format_money_it(diff))
        else:
            # Quando gli investimenti superano i debiti, mostra il valore in verde senza segno meno.
            self.fin_inv_diff_value_var.set(self._format_money_it(abs(diff)))
        if self.fin_inv_diff_label is not None:
            self.fin_inv_diff_label.config(fg=FG_NEGATIVE if diff > 0 else FG_SOMMA)

    def _build_data_table(self, parent: tk.Frame, table_key: str) -> dict[str, tk.Widget]:
        frame = tk.Frame(parent, bg=BG_TABLE)
        frame.pack(fill="both", expand=True, padx=8, pady=8)

        if table_key in MAIN_TABLE_KEYS:
            controls = tk.Frame(frame, bg=BG_TABLE)
            controls.pack(fill="x", pady=(0, 8))
            tk.Label(controls, text="Anno", font=FONT_SMALL, bg=BG_TABLE, fg=FG_HEADER).pack(side="left")
            year_cb = ttk.Combobox(
                controls,
                textvariable=self.main_year_var,
                state="readonly",
                width=12,
                values=[],
            )
            year_cb.pack(side="left", padx=(8, 0))
            year_cb.bind("<<ComboboxSelected>>", lambda _e: self._on_main_year_change())
            self.main_year_cbs[table_key] = year_cb

            # Bottone Grafici
            _key = table_key  # capture for lambda
            tk.Button(
                controls,
                text="📈 Grafici",
                font=FONT_TAB,
                fg=FG_HEADER,
                bg=BG_FRAME,
                activeforeground=FG_HEADER,
                activebackground=SEL_BG,
                relief="flat",
                bd=0,
                padx=14,
                pady=4,
                cursor="hand2",
                command=lambda k=_key: self._open_main_tab_chart_window(k),
            ).pack(side="left", padx=(16, 0))

        canvas = tk.Canvas(frame, bg=BG_TABLE, highlightthickness=0)
        vsb = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=canvas.xview)
        canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        canvas.pack(side="left", fill="both", expand=True)

        body = tk.Frame(canvas, bg=BG_TABLE)
        window_id = canvas.create_window((0, 0), window=body, anchor="nw")

        def _refresh_scrollregion(_event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _sync_width(event):
            if body.winfo_reqwidth() < event.width:
                canvas.itemconfigure(window_id, width=event.width)
            else:
                canvas.itemconfigure(window_id, width=body.winfo_reqwidth())

        body.bind("<Configure>", _refresh_scrollregion)
        canvas.bind("<Configure>", _sync_width)

        return {"frame": frame, "canvas": canvas, "body": body}

    def _init_main_year_filters(self):
        options = list(self.main_tab_years)
        for cb in self.main_year_cbs.values():
            cb["values"] = options

        preferred = self.current_year_sheet if self.current_year_sheet in options else (options[-1] if options else "")
        if preferred and self.main_year_var.get() not in options:
            self.main_year_var.set(preferred)

    def _get_selected_main_year(self) -> str:
        selected = self.main_year_var.get().strip()
        if selected in self.tables_by_year:
            return selected
        if self.current_year_sheet in self.tables_by_year:
            return self.current_year_sheet
        return self.main_tab_years[-1] if self.main_tab_years else ""

    def _refresh_main_tables_for_year(self):
        selected_year = self._get_selected_main_year()
        year_tables = self.tables_by_year.get(selected_year, {})
        if not isinstance(year_tables, dict):
            return

        for key in MAIN_TABLE_KEYS:
            view = self.table_views.get(key)
            df = year_tables.get(key)
            if view is None or df is None:
                continue
            self._populate_data_table(view, df, table_key=key)

    def _on_main_year_change(self):
        self._refresh_main_tables_for_year()

    def _is_numeric_value(self, value) -> bool:
        return isinstance(value, Real) and not isinstance(value, bool)

    def _is_zero_value(self, value) -> bool:
        return self._is_numeric_value(value) and abs(float(value)) < 1e-9

    def _format_number_it(self, value: float, decimals: int = 2) -> str:
        us_text = f"{float(value):,.{decimals}f}"
        return us_text.replace(",", "#").replace(".", ",").replace("#", ".")

    def _format_number_it_compact(self, value: float, max_decimals: int = 6) -> str:
        us_text = f"{float(value):,.{max_decimals}f}".rstrip("0").rstrip(".")
        return us_text.replace(",", "#").replace(".", ",").replace("#", ".")

    def _format_money_it(self, value: float, prefix: str = "EUR") -> str:
        return f"{prefix} {self._format_number_it(value, 2)}"

    def _format_date_with_weekday_it(self, value: date) -> str:
        weekday_it = GIORNI_SETTIMANA_IT[value.weekday()]
        return f"{value.strftime('%d/%m/%Y')} ({weekday_it})"

    def _format_signed_number_it(self, value: float, decimals: int = 2) -> str:
        sign = "+" if value >= 0 else ""
        return f"{sign}{self._format_number_it(value, decimals)}"

    def _parse_localized_number(self, raw: str) -> float | None:
        text = str(raw).strip().replace("€", "").replace("EUR", "").replace(" ", "")
        if not text:
            return None
        try:
            if "," in text and "." in text:
                # Se la virgola è più a destra, probabile formato IT (1.234,56)
                if text.rfind(",") > text.rfind("."):
                    normalized = text.replace(".", "").replace(",", ".")
                else:
                    # Formato US (1,234.56)
                    normalized = text.replace(",", "")
            elif "," in text:
                normalized = text.replace(".", "").replace(",", ".")
            else:
                normalized = text.replace(",", "")
            return float(normalized)
        except ValueError:
            return None

    def _format_table_value(self, column: str, value) -> str:
        if column != "Piattaforma" and self._is_numeric_value(value):
            return self._format_money_it(float(value), prefix="€")
        return str(value)

    def _get_table_cell_color(self, column: str, value, *, is_total_row: bool, is_zero_row: bool) -> str:
        if is_total_row:
            return FG_SOMMA
        if column == "Piattaforma":
            return "#585b70" if is_zero_row else FG
        if not self._is_numeric_value(value):
            return FG
        numeric_value = float(value)
        if abs(numeric_value) < 1e-9:
            return "#585b70"
        return FG_SOMMA if numeric_value > 0 else FG_NEGATIVE

    def _populate_data_table(self, table_view: dict[str, tk.Widget], df, table_key: str | None = None):
        body = table_view["body"]
        canvas = table_view["canvas"]

        for child in body.winfo_children():
            child.destroy()

        df = df.copy()

        show_total_column = table_key != "inv_guad"

        # Aggiungi colonna TOTALE se non esiste (tranne per Inv + Guad)
        cols = list(df.columns)
        if show_total_column and "TOTALE" not in cols:
            mesi_cols = [col for col in cols if col in MESI]
            df["TOTALE"] = df[mesi_cols].apply(
                lambda row: sum(float(self._safe_value(v)) for v in row), axis=1
            )
            cols = list(df.columns)

        if not show_total_column and "TOTALE" in cols:
            df = df.drop(columns=["TOTALE"])
            cols = list(df.columns)

        # Ultima cella: la SOMMA della colonna TOTALE deve riflettere sempre
        # la somma dei totali di riga (escludendo la riga SOMMA stessa).
        if "Piattaforma" in cols and "TOTALE" in cols:
            is_sum_row = df["Piattaforma"].astype(str).str.strip().str.upper() == "SOMMA"
            grand_total = df.loc[~is_sum_row, "TOTALE"].apply(self._safe_value).sum()
            if is_sum_row.any():
                df.loc[is_sum_row, "TOTALE"] = grand_total

        numeric_cols = [col for col in cols if col != "Piattaforma"]

        for col_idx, col in enumerate(cols):
            # Nel tab Inv + Guad teniamo colonne un filo più compatte.
            if table_key == "inv_guad":
                col_width = 150 if col == "Piattaforma" else 100
            else:
                col_width = 160 if col == "Piattaforma" else (130 if col == "TOTALE" else 110)
            body.grid_columnconfigure(col_idx, minsize=col_width, weight=0)
            tk.Label(
                body,
                text=col,
                font=FONT_TAB,
                bg=BG_FRAME,
                fg=FG_HEADER,
                padx=12,
                pady=8,
                anchor="w" if col == "Piattaforma" else "center",
                highlightthickness=1,
                highlightbackground=BG,
            ).grid(row=0, column=col_idx, sticky="nsew")

        for row_idx, (_, row) in enumerate(df.iterrows(), start=1):
            platform_name = str(row["Piattaforma"])
            is_total_row = platform_name.upper() == "SOMMA"
            is_zero_row = all(self._is_zero_value(row[col]) for col in numeric_cols)
            row_font = ("Segoe UI", 10, "bold") if is_total_row else FONT_TABLE

            for col_idx, col in enumerate(cols):
                cell_value = row[col]
                tk.Label(
                    body,
                    text=self._format_table_value(col, cell_value),
                    font=row_font,
                    bg=BG_TABLE,
                    fg=self._get_table_cell_color(col, cell_value, is_total_row=is_total_row, is_zero_row=is_zero_row),
                    padx=12,
                    pady=7,
                    anchor="w" if col == "Piattaforma" else "center",
                    highlightthickness=1,
                    highlightbackground=BG,
                ).grid(row=row_idx, column=col_idx, sticky="nsew")

        body.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))

    def _safe_value(self, value) -> float:
        """Converte un valore a float in modo sicuro, ritorna 0.0 se fallisce."""
        try:
            if value is None or value == "":
                return 0.0
            return float(value)
        except (ValueError, TypeError):
            return 0.0

    def _build_statusbar(self):
        bar = tk.Frame(self, bg=BG_FRAME, height=24)
        bar.pack(fill="x", side="bottom")
        self.lbl_status = tk.Label(bar, text="", font=FONT_SMALL,
                                   bg=BG_FRAME, fg=FG, anchor="w")
        self.lbl_status.pack(side="left", padx=10)

    def _build_graphs_placeholder(self, parent: tk.Frame):
        wrapper = tk.Frame(parent, bg=BG_TABLE)
        wrapper.pack(fill="both", expand=True, padx=16, pady=16)

        controls = tk.Frame(wrapper, bg=BG_TABLE)
        controls.pack(fill="x")

        tk.Label(controls, text="Piattaforma", font=FONT_SMALL, bg=BG_TABLE, fg=FG_HEADER).pack(side="left")
        self.graph_platform_cb = ttk.Combobox(
            controls,
            textvariable=self.graph_platform_var,
            state="readonly",
            width=22,
            values=[],
        )
        self.graph_platform_cb.pack(side="left", padx=(8, 20))
        self.graph_platform_cb.bind("<<ComboboxSelected>>", lambda _e: self._refresh_graph())

        tk.Label(controls, text="Mese", font=FONT_SMALL, bg=BG_TABLE, fg=FG_HEADER).pack(side="left")
        self.graph_month_cb = ttk.Combobox(
            controls,
            textvariable=self.graph_month_var,
            state="readonly",
            width=18,
            values=[],
        )
        self.graph_month_cb.pack(side="left", padx=(8, 0))
        self.graph_month_cb.bind("<<ComboboxSelected>>", lambda _e: self._refresh_graph())

        content = tk.Frame(wrapper, bg=BG_TABLE)
        content.pack(fill="both", expand=True, pady=(16, 0))

        self.graph_canvas = tk.Canvas(
            content,
            width=GRAPH_CANVAS_W,
            height=GRAPH_CANVAS_H,
            bg=BG_TABLE,
            highlightthickness=0,
        )
        self.graph_canvas.pack(side="left", padx=(0, 24), pady=8)

        right = tk.Frame(content, bg=BG_TABLE)
        right.pack(side="left", fill="both", expand=True)

        tk.Label(right, text="Progresso Obiettivo", font=("Segoe UI", 12, "bold"), bg=BG_TABLE, fg=FG_HEADER).pack(anchor="w")
        tk.Label(right, textvariable=self.graph_info_var, font=FONT_TABLE, bg=BG_TABLE, fg=FG, justify="left").pack(anchor="w", pady=(8, 0))
        tk.Label(right, textvariable=self.graph_empty_var, font=FONT_SMALL, bg=BG_TABLE, fg=FG_ACCENT, justify="left").pack(anchor="w", pady=(8, 0))

    def _build_live_investments_tab(self, parent: tk.Frame):
        wrapper = tk.Frame(parent, bg=BG_TABLE)
        wrapper.pack(fill="both", expand=True, padx=16, pady=16)

        tk.Label(
            wrapper,
            text="Investimenti attuali vivi",
            font=("Segoe UI", 12, "bold"),
            bg=BG_TABLE,
            fg=FG_HEADER,
        ).pack(anchor="w")

        content = tk.Frame(wrapper, bg=BG_TABLE)
        content.pack(fill="both", expand=True, pady=(14, 0))

        # Layout a 2 colonne fisso: cumulativi a sinistra, dettaglio a destra.
        content.grid_columnconfigure(0, weight=1)
        content.grid_columnconfigure(1, weight=0, minsize=300)
        content.grid_rowconfigure(0, weight=1)

        left_col = tk.Frame(content, bg=BG_TABLE)
        left_col.grid(row=0, column=0, sticky="nsew")

        right_col = tk.Frame(content, bg=BG_TABLE)
        right_col.grid(row=0, column=1, sticky="ne", padx=(12, 0))

        card1 = tk.Frame(left_col, bg=BG_FRAME, padx=16, pady=12)
        card1.pack(anchor="w", fill="x", pady=(0, 8))
        tk.Label(card1, text="Bondora + Mintos", font=FONT_TAB, bg=BG_FRAME, fg=FG).pack(anchor="w")
        tk.Label(card1, textvariable=self.live_bm_value_var, font=("Segoe UI", 16, "bold"), bg=BG_FRAME, fg=FG_SOMMA).pack(anchor="w", pady=(6, 0))

        card2 = tk.Frame(left_col, bg=BG_FRAME, padx=16, pady=12)
        card2.pack(anchor="w", fill="x")
        tk.Label(card2, text="Bondora + Mintos + ReLender", font=FONT_TAB, bg=BG_FRAME, fg=FG).pack(anchor="w")
        tk.Label(card2, textvariable=self.live_bmr_value_var, font=("Segoe UI", 16, "bold"), bg=BG_FRAME, fg=FG_SOMMA).pack(anchor="w", pady=(6, 0))

        detail = tk.Frame(right_col, bg=BG_FRAME, padx=16, pady=12)
        detail.pack(anchor="n", fill="x")
        tk.Label(detail, text="Dettaglio piattaforme", font=FONT_TAB, bg=BG_FRAME, fg=FG_HEADER).pack(anchor="w", pady=(0, 8))

        row1 = tk.Frame(detail, bg=BG_FRAME)
        row1.pack(fill="x")
        tk.Label(row1, text="Bondora", font=FONT_TABLE, bg=BG_FRAME, fg=FG).pack(side="left")
        tk.Label(row1, textvariable=self.live_bondora_value_var, font=FONT_TABLE, bg=BG_FRAME, fg=FG_SOMMA).pack(side="right")

        row2 = tk.Frame(detail, bg=BG_FRAME)
        row2.pack(fill="x", pady=(4, 0))
        tk.Label(row2, text="Mintos", font=FONT_TABLE, bg=BG_FRAME, fg=FG).pack(side="left")
        tk.Label(row2, textvariable=self.live_mintos_value_var, font=FONT_TABLE, bg=BG_FRAME, fg=FG_SOMMA).pack(side="right")

        row3 = tk.Frame(detail, bg=BG_FRAME)
        row3.pack(fill="x", pady=(4, 0))
        tk.Label(row3, text="ReLender", font=FONT_TABLE, bg=BG_FRAME, fg=FG).pack(side="left")
        tk.Label(row3, textvariable=self.live_relender_value_var, font=FONT_TABLE, bg=BG_FRAME, fg=FG_SOMMA).pack(side="right")

    def _normalize_platform_name(self, name: str) -> str:
        # Uniforma le varianti tipo "ReLender", "Re-Lender", "Re Lender".
        return (
            str(name)
            .strip()
            .lower()
            .replace(" ", "")
            .replace("_", "")
            .replace("-", "")
        )

    def _safe_float(self, value):
        if not self._is_numeric_value(value):
            return None
        number = float(value)
        # NaN check senza dipendenze extra
        if number != number:
            return None
        return number

    def _get_current_platform_amount(self, platform_name: str, aliases: list[str] | None = None) -> float:
        inv_guad_df = self.tables.get("inv_guad")
        if inv_guad_df is None or inv_guad_df.empty or "Piattaforma" not in inv_guad_df.columns:
            return 0.0

        names = [platform_name] + (aliases or [])
        targets = {self._normalize_platform_name(name) for name in names}
        month_cols = [m for m in MESI if m in inv_guad_df.columns]
        if not month_cols:
            return 0.0

        platform_row = None
        for _, row in inv_guad_df.iterrows():
            row_name = self._normalize_platform_name(row.get("Piattaforma", ""))
            if row_name in targets:
                platform_row = row
                break

        if platform_row is None:
            return 0.0

        # Preferisce il mese corrente, altrimenti usa l'ultimo mese disponibile.
        current_month = MESI[datetime.now().month - 1]
        if current_month in month_cols:
            current_value = self._safe_float(platform_row.get(current_month))
            if current_value is not None:
                return current_value

        for month in reversed(month_cols):
            fallback_value = self._safe_float(platform_row.get(month))
            if fallback_value is not None:
                return fallback_value

        return 0.0

    def _refresh_live_investments_tab(self):
        bondora = self._get_current_platform_amount("Bondora")
        mintos = self._get_current_platform_amount("Mintos")
        relender = self._get_current_platform_amount(
            "ReLender",
            aliases=["Re Lender", "Re-Lender", "Relender"],
        )

        bm_total = bondora + mintos
        bmr_total = bm_total + relender

        self.live_bondora_value_var.set(self._format_money_it(bondora))
        self.live_mintos_value_var.set(self._format_money_it(mintos))
        self.live_relender_value_var.set(self._format_money_it(relender))
        self.live_bm_value_var.set(self._format_money_it(bm_total))
        self.live_bmr_value_var.set(self._format_money_it(bmr_total))

    def _build_progressive_tab(self, parent: tk.Frame):
        wrapper = tk.Frame(parent, bg=BG_TABLE)
        wrapper.pack(fill="both", expand=True, padx=16, pady=16)

        tk.Label(
            wrapper,
            text="Statistiche progressive",
            font=("Segoe UI", 12, "bold"),
            bg=BG_TABLE,
            fg=FG_HEADER,
        ).pack(anchor="w")

        content = tk.Frame(wrapper, bg=BG_TABLE)
        content.pack(fill="both", expand=True, pady=(10, 0))

        link = tk.Button(
            content,
            text="Confronto annuale",
            font=FONT_TAB,
            fg=FG_HEADER,
            bg=BG_FRAME,
            activeforeground=FG_HEADER,
            activebackground=SEL_BG,
            relief="flat",
            bd=0,
            padx=14,
            pady=8,
            cursor="hand2",
            command=self._go_to_gt_anno,
        )
        link.pack(side="top", anchor="w", padx=10, pady=(0, 8))

        link_mensile = tk.Button(
            content,
            text="Confronto mensile",
            font=FONT_TAB,
            fg=FG_HEADER,
            bg=BG_FRAME,
            activeforeground=FG_HEADER,
            activebackground=SEL_BG,
            relief="flat",
            bd=0,
            padx=14,
            pady=8,
            cursor="hand2",
            command=self._go_to_gpp_window,
        )
        link_mensile.pack(side="top", anchor="w", padx=10, pady=(0, 8))

        link_medie_mensili = tk.Button(
            content,
            text="Medie mensili",
            font=FONT_TAB,
            fg=FG_HEADER,
            bg=BG_FRAME,
            activeforeground=FG_HEADER,
            activebackground=SEL_BG,
            relief="flat",
            bd=0,
            padx=14,
            pady=8,
            cursor="hand2",
            command=self._go_to_mm_window,
        )
        link_medie_mensili.pack(side="top", anchor="w", padx=10, pady=(0, 8))

        link_previsionale = tk.Button(
            content,
            text="Previsionale",
            font=FONT_TAB,
            fg=FG_HEADER,
            bg=BG_FRAME,
            activeforeground=FG_HEADER,
            activebackground=SEL_BG,
            relief="flat",
            bd=0,
            padx=14,
            pady=8,
            cursor="hand2",
            command=self._go_to_pv_window,
        )
        link_previsionale.pack(side="top", anchor="w", padx=10, pady=(0, 8))

        link_confronto_totale = tk.Button(
            content,
            text="Confronto totale mensile",
            font=FONT_TAB,
            fg=FG_HEADER,
            bg=BG_FRAME,
            activeforeground=FG_HEADER,
            activebackground=SEL_BG,
            relief="flat",
            bd=0,
            padx=14,
            pady=8,
            cursor="hand2",
            command=self._go_to_ctm_window,
        )
        link_confronto_totale.pack(side="top", anchor="w", padx=10, pady=(0, 8))

        link_bondora_mensile = tk.Button(
            content,
            text="Previsionale mensile Bondora",
            font=FONT_TAB,
            fg=FG_HEADER,
            bg=BG_FRAME,
            activeforeground=FG_HEADER,
            activebackground=SEL_BG,
            relief="flat",
            bd=0,
            padx=14,
            pady=8,
            cursor="hand2",
            command=self._go_to_bmb_window,
        )
        link_bondora_mensile.pack(side="top", anchor="w", padx=10, pady=(0, 8))

        link_bondora_con_aggiunta = tk.Button(
            content,
            text="Previsionale Bondora con aggiunta",
            font=FONT_TAB,
            fg=FG_HEADER,
            bg=BG_FRAME,
            activeforeground=FG_HEADER,
            activebackground=SEL_BG,
            relief="flat",
            bd=0,
            padx=14,
            pady=8,
            cursor="hand2",
            command=self._go_to_pbca_window,
        )
        link_bondora_con_aggiunta.pack(side="top", anchor="w", padx=10, pady=(0, 8))

        link_icb = tk.Button(
            content,
            text="Interesse Composto Bondora",
            font=FONT_TAB,
            fg=FG_HEADER,
            bg=BG_FRAME,
            activeforeground=FG_HEADER,
            activebackground=SEL_BG,
            relief="flat",
            bd=0,
            padx=14,
            pady=8,
            cursor="hand2",
            command=self._go_to_icb_window,
        )
        link_icb.pack(side="top", anchor="w", padx=10, pady=(0, 8))

    def _build_bondora_evolution_tab(self, parent,):
        wrapper = tk.Frame(parent, bg=BG_TABLE)
        wrapper.pack(fill="both", expand=True, padx=16, pady=16)

        tk.Label(
            wrapper,
            text="Bondora Evolution",
            font=("Segoe UI", 12, "bold"),
            bg=BG_TABLE,
            fg=FG_HEADER,
        ).pack(anchor="w")

        controls = tk.Frame(wrapper, bg=BG_TABLE)
        controls.pack(fill="x", pady=(10, 0))

        tk.Label(controls, text="Cifra guadagnata", font=FONT_SMALL, bg=BG_TABLE, fg=FG_HEADER).pack(side="left")
        self.bondo_evo_daily_cb = ttk.Combobox(
            controls,
            textvariable=self.bondo_evo_daily_var,
            state="readonly",
            width=25,
            values=[],
        )
        self.bondo_evo_daily_cb.pack(side="left", padx=(8, 0))
        self.bondo_evo_daily_cb.bind("<<ComboboxSelected>>", lambda _e: self._refresh_bondo_evo_display())

        # Content frame con info a sinistra e grafico centrato
        content = tk.Frame(wrapper, bg=BG_TABLE)
        content.pack(fill="both", expand=True, pady=(16, 0))

        # Frame per visualizzare i dettagli a sinistra
        self.bondo_evo_info_frame = tk.Frame(content, bg=BG_TABLE)
        self.bondo_evo_info_frame.pack(side="left", fill="both", padx=(0, 32))

        charts_col = tk.Frame(content, bg=BG_TABLE)
        charts_col.pack(side="left", fill="y", padx=(16, 0), pady=(0, 8))

        tk.Label(
            charts_col,
            text="Completamento importo (obiettivo selezionato)",
            font=FONT_SMALL,
            bg=BG_TABLE,
            fg=FG_HEADER,
        ).pack(anchor="w")

        self.bondo_evo_graph_canvas = tk.Canvas(
            charts_col,
            width=GRAPH_CANVAS_W,
            height=GRAPH_CANVAS_H,
            bg=BG_TABLE,
            highlightthickness=0,
        )
        self.bondo_evo_graph_canvas.pack(anchor="w", pady=(4, 16))
        self.bondo_evo_graph_canvas.bind("<Configure>", lambda _e: self._schedule_bondo_evo_redraw())

        tk.Label(
            charts_col,
            text="Completamento giorni (prossimo obiettivo)",
            font=FONT_SMALL,
            bg=BG_TABLE,
            fg=FG_HEADER,
        ).pack(anchor="w")

        self.bondo_evo_next_graph_canvas = tk.Canvas(
            charts_col,
            width=GRAPH_CANVAS_W,
            height=GRAPH_CANVAS_H,
            bg=BG_TABLE,
            highlightthickness=0,
        )
        self.bondo_evo_next_graph_canvas.pack(anchor="w", pady=(4, 4))
        self.bondo_evo_next_graph_canvas.bind("<Configure>", lambda _e: self._schedule_bondo_evo_redraw())

        tk.Label(
            charts_col,
            textvariable=self.bondo_evo_next_info_var,
            font=FONT_SMALL,
            bg=BG_TABLE,
            fg=FG,
            justify="left",
        ).pack(anchor="w", pady=(2, 0))

    def _build_gt_anno_tab(self, parent: tk.Frame):
        wrapper = tk.Frame(parent, bg=BG_TABLE)
        wrapper.pack(fill="both", expand=True, padx=16, pady=16)

        header_row = tk.Frame(wrapper, bg=BG_TABLE)
        header_row.pack(fill="x")

        tk.Label(
            header_row,
            text="Sezione GT_ANNO",
            font=("Segoe UI", 12, "bold"),
            bg=BG_TABLE,
            fg=FG_HEADER,
        ).pack(side="left", anchor="w")

        tk.Button(
            header_row,
            text="<- Torna indietro",
            bg=BG_FRAME,
            fg=FG,
            activebackground=SEL_BG,
            activeforeground=FG_HEADER,
            relief="flat",
            padx=10,
            command=self._back_to_progressive_tab,
        ).pack(side="right")

        controls = tk.Frame(wrapper, bg=BG_TABLE)
        controls.pack(fill="x", pady=(12, 10))

        tk.Label(controls, text="Anno", font=FONT_SMALL, bg=BG_TABLE, fg=FG_HEADER).pack(side="left")
        self.gt_year_cb = ttk.Combobox(
            controls,
            textvariable=self.gt_year_var,
            state="readonly",
            width=12,
            values=[],
        )
        self.gt_year_cb.pack(side="left", padx=(8, 16))
        self.gt_year_cb.bind("<<ComboboxSelected>>", lambda _e: self._refresh_gt_anno_selection())

        tk.Label(controls, text="Piattaforma", font=FONT_SMALL, bg=BG_TABLE, fg=FG_HEADER).pack(side="left")
        self.gt_platform_cb = ttk.Combobox(
            controls,
            textvariable=self.gt_platform_var,
            state="readonly",
            width=20,
            values=[],
        )
        self.gt_platform_cb.pack(side="left", padx=(8, 16))
        self.gt_platform_cb.bind("<<ComboboxSelected>>", lambda _e: self._refresh_gt_anno_selection())

        tk.Label(controls, text="Tipo", font=FONT_SMALL, bg=BG_TABLE, fg=FG_HEADER).pack(side="left")
        self.gt_metric_cb = ttk.Combobox(
            controls,
            textvariable=self.gt_metric_label_var,
            state="readonly",
            width=24,
            values=[],
        )
        self.gt_metric_cb.pack(side="left", padx=(8, 0))
        self.gt_metric_cb.bind("<<ComboboxSelected>>", lambda _e: self._refresh_gt_anno_selection())

        tk.Label(
            wrapper,
            textvariable=self.gt_result_var,
            font=("Segoe UI", 16, "bold"),
            bg=BG_TABLE,
            fg=FG_SOMMA,
            justify="left",
        ).pack(anchor="w", pady=(16, 4))

        tk.Label(
            wrapper,
            textvariable=self.gt_hint_var,
            font=FONT_SMALL,
            bg=BG_TABLE,
            fg=FG,
            justify="left",
        ).pack(anchor="w")

        self.gt_compare_frame = tk.Frame(wrapper, bg=BG_TABLE)
        self.gt_compare_frame.pack(fill="both", expand=True, pady=(10, 0))

        vsb = ttk.Scrollbar(self.gt_compare_frame, orient="vertical")
        hsb = ttk.Scrollbar(self.gt_compare_frame, orient="horizontal")
        self.gt_compare_tree = ttk.Treeview(
            self.gt_compare_frame,
            yscrollcommand=vsb.set,
            xscrollcommand=hsb.set,
            selectmode="browse",
            height=8,
        )
        vsb.config(command=self.gt_compare_tree.yview)
        hsb.config(command=self.gt_compare_tree.xview)
        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        self.gt_compare_tree.pack(fill="both", expand=True)
        self.gt_compare_tree.tag_configure("positive", foreground="#a6e3a1")
        self.gt_compare_tree.tag_configure("negative", foreground="#f38ba8")
        self.gt_compare_tree.tag_configure("neutral", foreground=FG)

        self.gt_chart_frame = tk.Frame(wrapper, bg=BG_TABLE)
        self.gt_chart_frame.pack(fill="both", expand=True, pady=(10, 0))

    def _set_window_icon(self):
        """Imposta l'icona finestra con il simbolo $ se disponibile."""
        try:
            icon_path = _resource_path(os.path.join("assets", "dollar.png"))
            if os.path.exists(icon_path):
                self._icon_image = tk.PhotoImage(file=icon_path)
                self.iconphoto(True, self._icon_image)
        except Exception:
            # Fallback silenzioso: usa icona di default del sistema
            pass

    def _load_data(self):
        try:
            self._set_status("Connessione a Dropbox...")
            dbx = get_dropbox_client()
            self._set_status("Rilevamento anno corrente...")
            sheet_anno = detect_current_year_sheet(dbx)
            self._set_status(f"Download e parsing dati ({sheet_anno})...")
            tables = get_tables(dbx, sheet_anno)
            goals = get_fixed_platform_goals(dbx, sheet_anno)
            gt_anno = get_gt_anno_data(dbx)
            bondo_evo_data = get_bondo_evo_daily_values(dbx)
            gpp_data = get_gpp_anno_data(dbx)
            ctm_data = get_total_monthly_comparison_data(dbx)
            yearly_main_tables = get_yearly_main_tables_data(dbx, sheet_anno)
            fin_inv_debts = get_fin_inv_debts(dbx, sheet_anno)
            self.after(0, lambda: self._populate_all(
                tables,
                goals,
                gt_anno,
                bondo_evo_data,
                gpp_data,
                ctm_data,
                yearly_main_tables,
                fin_inv_debts,
                sheet_anno,
            ))
            self._set_status("Dati caricati con successo.")
        except Exception as ex:
            self.after(0, lambda err=ex: messagebox.showerror("Errore", str(err)))
            self._set_status(f"Errore: {ex}")

    def _populate_all(self, tables: dict, goals: dict[str, float], gt_anno: dict[str, object],
                      bondo_evo_data: dict[float, dict[str, object]], gpp_data: dict[str, object],
                      ctm_data: dict[str, object],
                      yearly_main_tables: dict[str, object],
                      fin_inv_debts: dict[str, float],
                      sheet_anno: str):
        self.tables = tables
        self.platform_goals = goals
        self.gt_data = gt_anno
        self.bondo_evo_data = bondo_evo_data
        self.gpp_data = gpp_data
        self.ctm_data = ctm_data
        self.fin_inv_debts = fin_inv_debts if isinstance(fin_inv_debts, dict) else {"fin_home": 0.0, "fin_car": 0.0, "total": 0.0}
        self.tables_by_year = {
            str(year): year_tables
            for year, year_tables in (yearly_main_tables.get("tables_by_year", {}) if isinstance(yearly_main_tables, dict) else {}).items()
            if isinstance(year_tables, dict)
        }
        self.main_tab_years = [
            str(year) for year in (yearly_main_tables.get("years", []) if isinstance(yearly_main_tables, dict) else [])
            if str(year) in self.tables_by_year
        ]
        if not self.main_tab_years:
            self.tables_by_year = {sheet_anno: tables}
            self.main_tab_years = [sheet_anno]
        if sheet_anno not in self.tables_by_year:
            self.tables_by_year[sheet_anno] = tables
            if sheet_anno not in self.main_tab_years:
                self.main_tab_years.append(sheet_anno)
                self.main_tab_years.sort(key=int)
        self.current_year_sheet = sheet_anno

        # Aggiorna titolo finestra e header con l'anno rilevato
        self.title(f"Own Finance – {sheet_anno}")
        self.lbl_header.config(text=f"Own Finance  —  Riepilogo {sheet_anno}")

        self._init_main_year_filters()
        self._refresh_main_tables_for_year()
        self._init_graph_filters()
        self._refresh_graph()
        self._init_gt_anno_filters()
        self._refresh_gt_anno_selection()
        self._init_bondo_evo_filters()
        self._refresh_bondo_evo_display()
        self._refresh_live_investments_tab()
        self._refresh_fin_inv_tab()
        self._refresh_ntb_display()
        if self.ctm_window is not None and self.ctm_window.winfo_exists():
            self._render_ctm_table()
        if self.ctm_graph_window is not None and self.ctm_graph_window.winfo_exists():
            self._init_ctm_graph_filters()
            self._render_ctm_graph()
        if self.icb_window is not None and self.icb_window.winfo_exists():
            self._render_icb_table()
        ts = datetime.now().strftime("%d/%m/%Y %H:%M")
        self.lbl_update.config(text=f"Aggiornato: {ts}")

    def _init_graph_filters(self):
        inv_guad_df = self.tables.get("inv_guad")
        if inv_guad_df is None or inv_guad_df.empty:
            self.graph_empty_var.set("Tabella inv_guad non disponibile.")
            return

        available_platforms = []
        for platform in self.platform_goals.keys():
            found = inv_guad_df[inv_guad_df["Piattaforma"].astype(str).str.strip() == platform]
            if not found.empty:
                available_platforms.append(platform)

        available_months = [m for m in MESI if m in inv_guad_df.columns]

        if self.graph_platform_cb is not None:
            self.graph_platform_cb["values"] = available_platforms
        if self.graph_month_cb is not None:
            self.graph_month_cb["values"] = available_months

        if available_platforms and not self.graph_platform_var.get():
            self.graph_platform_var.set(available_platforms[0])

        if available_months and not self.graph_month_var.get():
            current_month = MESI[datetime.now().month - 1]
            self.graph_month_var.set(current_month if current_month in available_months else available_months[0])

    def _refresh_graph(self):
        if self.graph_canvas is None:
            return

        platform = self.graph_platform_var.get().strip()
        month = self.graph_month_var.get().strip()
        inv_guad_df = self.tables.get("inv_guad")

        if not platform or not month or inv_guad_df is None or inv_guad_df.empty:
            self.graph_canvas.delete("all")
            self.graph_info_var.set("Seleziona piattaforma e mese.")
            self.graph_empty_var.set("Dati non ancora disponibili.")
            return

        row = inv_guad_df[inv_guad_df["Piattaforma"].astype(str).str.strip() == platform]
        if row.empty or month not in inv_guad_df.columns:
            self.graph_canvas.delete("all")
            self.graph_info_var.set("Nessun dato disponibile per la selezione.")
            self.graph_empty_var.set("Controlla piattaforma/mese nel file excel.")
            return

        current_val = float(row.iloc[0][month])
        goal = float(self.platform_goals.get(platform, 0.0))

        if goal <= 0:
            self.graph_canvas.delete("all")
            self.graph_info_var.set(
                f"Piattaforma: {platform}\nMese: {month}\nObiettivo non valido (<= 0)."
            )
            self.graph_empty_var.set("Controlla i valori obiettivo in G37/G38.")
            return

        completed_ratio = max(0.0, min(current_val / goal, 1.0))
        completed_val = max(0.0, min(current_val, goal))
        remaining_val = max(0.0, goal - completed_val)
        extra_val = max(0.0, current_val - goal)

        self._draw_pie_chart(completed_ratio)

        details = (
            f"Piattaforma: {platform}\n"
            f"Mese: {month}\n"
            f"Completato (inv_guad): {self._format_money_it(current_val)}\n"
            f"Obiettivo: {self._format_money_it(goal)}\n"
            f"Copertura: {completed_ratio * 100:.1f}%"
        )
        self.graph_info_var.set(details)
        if extra_val > 0:
            self.graph_empty_var.set(f"Sforamento obiettivo: {self._format_money_it(extra_val)}")
        else:
            self.graph_empty_var.set(f"Residuo: {self._format_money_it(remaining_val)}")

    def _draw_pie_chart(self, completed_ratio: float):
        if self.graph_canvas is None:
            return

        c = self.graph_canvas
        c.delete("all")

        cw = max(240, int(c.winfo_width() or GRAPH_CANVAS_W))
        ch = max(240, int(c.winfo_height() or GRAPH_CANVAS_H))
        diameter = max(PIE_MIN_DIAMETER, min(PIE_MAX_DIAMETER, min(cw, ch) - (PIE_MARGIN * 2 + 26)))

        x0 = (cw - diameter) / 2
        y0 = PIE_MARGIN
        x1 = x0 + diameter
        y1 = y0 + diameter
        extent = 360 * completed_ratio

        c.create_oval(x0, y0, x1, y1, fill=FG_RESIDUO, outline="")
        if extent > 0:
            c.create_arc(x0, y0, x1, y1, start=90, extent=-extent, fill=FG_SOMMA, outline="")

        c.create_text((x0 + x1) / 2, (y0 + y1) / 2, text=f"{completed_ratio * 100:.1f}%", fill=FG_PERCENT, font=("Segoe UI", 18, "bold"))

        legend_y = min(ch - 14, y1 + 16)
        c.create_rectangle(40, legend_y - 7, 54, legend_y + 7, fill=FG_SOMMA, outline="")
        c.create_text(110, legend_y, text="Completato", fill=FG, font=FONT_SMALL)
        c.create_rectangle(cw - 130, legend_y - 7, cw - 116, legend_y + 7, fill=FG_RESIDUO, outline="")
        c.create_text(cw - 60, legend_y, text="Residuo", fill=FG, font=FONT_SMALL)


    def _set_status(self, msg: str):
        self.after(0, lambda: self.lbl_status.config(text=msg))

    def _refresh_all_data(self):
        """Invalida la cache e ricarica i dati da Dropbox in background."""
        invalidate_cache()
        self._set_status("Aggiornamento dati in corso…")
        threading.Thread(target=self._load_data, daemon=True).start()

    def _go_to_gt_anno(self):
        if self.gt_window is not None and self.gt_window.winfo_exists():
            self.gt_window.deiconify()
            self.gt_window.lift()
            self.gt_window.focus_force()
            return

        self.gt_window = tk.Toplevel(self)
        self.gt_window.title("Own Finance - GT_ANNO")
        self.gt_window.geometry("900x420")
        self.gt_window.configure(bg=BG_TABLE)
        self.gt_window.minsize(800, 480)
        self.gt_window.protocol("WM_DELETE_WINDOW", self._close_gt_anno_window)

        self._build_gt_anno_tab(self.gt_window)
        self._init_gt_anno_filters()
        self._refresh_gt_anno_selection()

        if self.gt_year_cb is not None:
            self.gt_year_cb.focus_set()

    def _close_gt_anno_window(self):
        if self.gt_window is not None and self.gt_window.winfo_exists():
            self.gt_window.destroy()
        self.gt_window = None
        self.gt_year_cb = None
        self.gt_platform_cb = None
        self.gt_metric_cb = None
        self._refocus_main()

    def _back_to_progressive_tab(self):
        """Ritorna al tab Statistiche progressive e chiude la finestra GT_ANNO."""
        if self.gt_window is not None and self.gt_window.winfo_exists():
            self._close_gt_anno_window()

        frame = self.tab_frames.get("statistiche_progressive")
        if frame is not None:
            self.notebook.select(frame)
        self._refocus_main()

    # ── Data population and refresh ─────────────────────────────

    def _init_gt_anno_filters(self):
        years = self.gt_data.get("years", []) if isinstance(self.gt_data, dict) else []
        raw_platforms = self.gt_data.get("platforms", []) if isinstance(self.gt_data, dict) else []
        # Nasconde le righe aggregate dal filtro piattaforme; la vista aggregata e' gestita da "Tutte".
        platforms = [
            p for p in raw_platforms
            if str(p).strip().upper().replace(" ", "_") not in {"MEDIA_TOTALE", "SOMMA", "TOTALE"}
        ]
        platforms_options = ["Tutte"] + platforms
        metrics_map = self.gt_data.get("metrics", {}) if isinstance(self.gt_data, dict) else {}
        metric_labels = list(metrics_map.keys())
        year_options = list(years) + ["Anno Per Anno"]

        if self.gt_year_cb is not None:
            self.gt_year_cb["values"] = year_options
        if self.gt_platform_cb is not None:
            self.gt_platform_cb["values"] = platforms_options
        if self.gt_metric_cb is not None:
            self.gt_metric_cb["values"] = metric_labels

        if years and not self.gt_year_var.get():
            self.gt_year_var.set(years[-1])
        if platforms_options and not self.gt_platform_var.get():
            self.gt_platform_var.set(platforms_options[0])
        if metric_labels and not self.gt_metric_label_var.get():
            # Default: "Guadagni totali" se presente, altrimenti primo elemento
            preferred = "Guadagni totali" if "Guadagni totali" in metric_labels else metric_labels[0]
            self.gt_metric_label_var.set(preferred)

    def _clear_bar_chart(self):
        """Rimuove l'istogramma matplotlib se presente."""
        if self.gt_mpl_canvas is not None:
            try:
                self.gt_mpl_canvas.get_tk_widget().destroy()
            except Exception:
                pass
            self.gt_mpl_canvas = None
        if self.gt_chart_frame is not None:
            for widget in self.gt_chart_frame.winfo_children():
                widget.destroy()

    def _draw_bar_chart(self, years: list, bar_data: dict, title: str):
        """Disegna un istogramma raggruppato (una serie per piattaforma, o singola serie)."""
        if self.gt_chart_frame is None:
            return
        self._clear_bar_chart()

        bg_color = BG_TABLE
        fg_color = FG
        header_color = FG_HEADER

        fig, ax = plt.subplots(figsize=(7, 3.2))
        fig.patch.set_facecolor(bg_color)
        ax.set_facecolor(bg_color)

        n_series = len(bar_data)
        n_years = len(years)
        import numpy as np
        x = np.arange(n_years)
        bar_width = max(0.12, min(0.7 / n_series, 0.35)) if n_series > 1 else 0.45
        offsets = np.linspace(-(n_series - 1) / 2 * bar_width, (n_series - 1) / 2 * bar_width, n_series)

        palette = [
            "#89b4fa", "#a6e3a1", "#f38ba8", "#fab387",
            "#cba6f7", "#f9e2af", "#94e2d5", "#eba0ac",
        ]

        for i, (label, values) in enumerate(bar_data.items()):
            color = palette[i % len(palette)]
            bars = ax.bar(x + offsets[i], values, width=bar_width, label=label, color=color, alpha=0.88)
            # Etichetta sul top della barra
            for bar_rect, val in zip(bars, values):
                if val > 0:
                    label_text = self._format_number_it_compact(val, max_decimals=6)
                    ax.text(
                        bar_rect.get_x() + bar_rect.get_width() / 2,
                        bar_rect.get_height() + max(values) * 0.01,
                        label_text,
                        ha="center", va="bottom",
                        fontsize=7, color=fg_color,
                    )

        ax.set_xticks(x)
        ax.set_xticklabels([str(y) for y in years], color=fg_color, fontsize=9)
        ax.tick_params(axis="y", colors=fg_color, labelsize=8)
        ax.spines["bottom"].set_color(fg_color)
        ax.spines["left"].set_color(fg_color)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.yaxis.label.set_color(fg_color)
        ax.set_ylabel("EUR", color=fg_color, fontsize=9)
        ax.set_title(title, color=header_color, fontsize=10, pad=8)
        ax.grid(axis="y", color="#585b70", linestyle="--", linewidth=0.5, alpha=0.6)

        if n_series > 1:
            legend = ax.legend(fontsize=8, facecolor=bg_color, edgecolor="#585b70", labelcolor=fg_color)

        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=self.gt_chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        self.gt_mpl_canvas = canvas

    def _hide_compare_table(self):
        """Nasconde il frame di confronto anni."""
        if self.gt_compare_frame is not None:
            self.gt_compare_frame.pack_forget()

    def _show_compare_table(self):
        """Mostra il frame di confronto anni (prima del chart frame)."""
        if self.gt_compare_frame is not None:
            # Re-pack prima del chart frame
            self.gt_compare_frame.pack(fill="both", expand=False, pady=(10, 0),
                                       before=self.gt_chart_frame)

    def _populate_compare_table(self, ref_value: float, ref_year, other_years: list,
                                 df, agg_row, platform: str, get_non_agg_df_fn):
        """Popola la tabella di confronto con delta rispetto agli altri anni."""
        tree = self.gt_compare_tree
        if tree is None:
            return

        tree.delete(*tree.get_children())
        tree["columns"] = ["Anno", "Valore", "Delta"]
        tree["show"] = "headings"
        tree.heading("Anno", text="Anno")
        tree.heading("Valore", text="Valore (EUR)")
        tree.heading("Delta", text=f"Δ {ref_year} vs. anno")
        tree.column("Anno", width=80, anchor="center")
        tree.column("Valore", width=140, anchor="center")
        tree.column("Delta", width=200, anchor="center")

        for other_year in sorted(other_years):
            if platform == "Tutte" and (agg_row is None or (hasattr(agg_row, "empty") and agg_row.empty)):
                other_value = float(get_non_agg_df_fn()[other_year].sum())
            else:
                try:
                    other_value = float(agg_row.iloc[0][other_year])
                except (KeyError, IndexError):
                    continue

            # delta = anno selezionato - anno di confronto
            delta = ref_value - other_value
            delta_str = self._format_signed_number_it(delta)
            tag = "positive" if delta > 0 else ("negative" if delta < 0 else "neutral")
            tree.insert("", "end", values=(
                str(other_year),
                self._format_number_it(other_value, 2),
                delta_str,
            ), tags=(tag,))

    def _refresh_gt_anno_selection(self):
        if not isinstance(self.gt_data, dict) or not self.gt_data:
            self.gt_result_var.set("Dati GT_ANNO non disponibili")
            self.gt_hint_var.set("Controlla che il foglio GT_ANNO esista nel file Dropbox.")
            self._clear_bar_chart()
            return

        year = self.gt_year_var.get().strip()
        platform = self.gt_platform_var.get().strip()
        metric_label = self.gt_metric_label_var.get().strip()

        raw_metrics_map = self.gt_data.get("metrics", {})
        raw_tables = self.gt_data.get("tables", {})
        metrics_map = raw_metrics_map if isinstance(raw_metrics_map, dict) else {}
        tables = raw_tables if isinstance(raw_tables, dict) else {}
        metric_key = metrics_map.get(metric_label)

        if not year or not platform or not metric_key:
            self.gt_result_var.set("Seleziona anno, piattaforma e tipo")
            self.gt_hint_var.set("")
            self._clear_bar_chart()
            return

        df = tables.get(metric_key)
        if df is None or df.empty:
            self.gt_result_var.set("Valore non disponibile")
            self.gt_hint_var.set("La combinazione scelta non e' presente nel foglio GT_ANNO.")
            self._clear_bar_chart()
            return

        # Helper per ricavare righe aggregate / piattaforma
        def get_agg_row():
            labels = df["Piattaforma"].astype(str).str.strip()
            normalized = labels.str.upper().str.replace(" ", "_", regex=False)
            agg_mask = normalized.isin(["MEDIA_TOTALE", "SOMMA", "TOTALE"])
            return df.loc[agg_mask].head(1) if agg_mask.any() else None

        def get_platform_row(p):
            return df[df["Piattaforma"].astype(str).str.strip() == p]

        def get_non_agg_df():
            labels = df["Piattaforma"].astype(str).str.strip().str.upper().str.replace(" ", "_", regex=False)
            return df.loc[~labels.isin(["MEDIA_TOTALE", "SOMMA", "TOTALE"])]

        if year == "Anno Per Anno":
            valid_years = [y for y in self.gt_data.get("years", []) if y in df.columns]
            if not valid_years:
                self.gt_result_var.set("Nessun anno disponibile")
                self.gt_hint_var.set("Non ci sono anni validi con dati numerici per questa tabella.")
                self._clear_bar_chart()
                self._hide_compare_table()
                return

            # Nasconde tabella confronto, mostra istogramma
            self._hide_compare_table()

            if platform == "Tutte":
                base_df = get_non_agg_df()
                bar_data = {}
                for _, prow in base_df.iterrows():
                    plat_name = str(prow["Piattaforma"]).strip()
                    vals = [float(prow[y]) if y in prow.index else 0.0 for y in valid_years]
                    if any(v != 0 for v in vals):
                        bar_data[plat_name] = vals
                title = f"{metric_label} – Tutte le piattaforme – anno per anno"
            else:
                row = get_platform_row(platform)
                if row.empty:
                    self.gt_result_var.set("Piattaforma non trovata")
                    self.gt_hint_var.set("La piattaforma selezionata non compare nella tabella.")
                    self._clear_bar_chart()
                    return
                vals = [float(row.iloc[0][y]) if y in row.columns else 0.0 for y in valid_years]
                bar_data = {platform: vals}
                title = f"{metric_label} – {platform} – anno per anno"

            self._draw_bar_chart(valid_years, bar_data, title)
            self.gt_result_var.set("")
            self.gt_hint_var.set(title)
            return

        # ── Anno specifico: valore + tabella confronto con gli altri anni ──
        self._clear_bar_chart()
        self._show_compare_table()

        if platform == "Tutte":
            agg_row = get_agg_row()
        else:
            agg_row = get_platform_row(platform)
            if agg_row.empty:
                self.gt_result_var.set("Piattaforma non trovata")
                self.gt_hint_var.set("La piattaforma selezionata non compare nella tabella.")
                self._hide_compare_table()
                return

        if year not in df.columns:
            self.gt_result_var.set("Valore non disponibile")
            self.gt_hint_var.set("La combinazione scelta non e' presente nel foglio GT_ANNO.")
            self._hide_compare_table()
            return

        if platform == "Tutte" and (agg_row is None or agg_row.empty):
            ref_value = float(get_non_agg_df()[year].sum())
        else:
            ref_value = float(agg_row.iloc[0][year])

        self.gt_result_var.set(self._format_money_it(ref_value))
        self.gt_hint_var.set(f"{metric_label} - {platform} - anno {year}")

        # Popola la tabella di confronto con tutti gli altri anni
        valid_years = self.gt_data.get("years", [])
        other_years = [y for y in valid_years if y != year and y in df.columns]
        self._populate_compare_table(ref_value, year, other_years, df, agg_row, platform, get_non_agg_df)

    def _init_bondo_evo_filters(self):
        """Carica i valori giornalieri di Bondora nel menu a tendina."""
        if not self.bondo_evo_data:
            self.bondo_evo_daily_var.set("")
            if self.bondo_evo_daily_cb is not None:
                self.bondo_evo_daily_cb["values"] = []
            return

        sorted_values = get_bondo_evo_selectable_targets(self.bondo_evo_data)
        sorted_display = [self._format_money_it(val, prefix="€") for val in sorted_values]

        if self.bondo_evo_daily_cb is not None:
            self.bondo_evo_daily_cb["values"] = sorted_display

        current_value = self.bondo_evo_daily_var.get()
        if sorted_display and current_value not in sorted_display:
            next_target = get_bondo_evo_next_unreached_target(self.bondo_evo_data)
            if next_target is not None:
                next_daily = float(next_target[0])
                self.bondo_evo_daily_var.set(self._format_money_it(next_daily, prefix="€"))
            else:
                self.bondo_evo_daily_var.set(sorted_display[0])

    def _on_notebook_tab_changed(self, _event=None):
        if self._is_bondora_evolution_tab_selected():
            self._schedule_bondo_evo_redraw()

    def _is_bondora_evolution_tab_selected(self) -> bool:
        frame = self.tab_frames.get("bondora_evolution")
        if frame is None or not hasattr(self, "notebook"):
            return False
        try:
            return self.notebook.select() == str(frame)
        except tk.TclError:
            return False

    def _schedule_bondo_evo_redraw(self):
        if not self.bondo_evo_data or not self.bondo_evo_daily_var.get().strip():
            return
        if self._bondo_evo_redraw_job is not None:
            try:
                self.after_cancel(self._bondo_evo_redraw_job)
            except tk.TclError:
                pass
        self._bondo_evo_redraw_job = self.after_idle(self._redraw_bondo_evo_if_visible)

    def _redraw_bondo_evo_if_visible(self):
        self._bondo_evo_redraw_job = None
        if self._is_bondora_evolution_tab_selected():
            self._refresh_bondo_evo_display()

    def _draw_pie_on_canvas(self, canvas: tk.Canvas, cap_pr: float, reached: float, size_scale: float = 1.0):
        """Disegna un grafico a torta generico su qualsiasi canvas."""
        c = canvas
        c.delete("all")
        cw = int(c.winfo_width() or 0)
        ch = int(c.winfo_height() or 0)
        if cw <= 2:
            cw = int(c.winfo_reqwidth() or GRAPH_CANVAS_W)
        if ch <= 2:
            ch = int(c.winfo_reqheight() or GRAPH_CANVAS_H)
        cx, cy = cw // 2, ch // 2
        scale = max(0.5, min(float(size_scale), 1.0))
        base_diameter = min(PIE_MIN_DIAMETER, cw - PIE_MARGIN * 2)
        diameter = max(96, int(base_diameter * scale))
        radius = diameter // 2
        x0 = cx - radius
        y0 = cy - radius
        x1 = cx + radius
        y1 = cy + radius
        if cap_pr > 0:
            completed_ratio = max(0.0, min(reached / cap_pr, 1.0))
        else:
            completed_ratio = 0.0
        extent = min(359.9, completed_ratio * 360)
        c.create_oval(x0, y0, x1, y1, fill=FG_RESIDUO, outline="")
        if extent > 0:
            c.create_arc(x0, y0, x1, y1, start=90, extent=-extent, fill=FG_SOMMA, outline="")
        c.create_text((x0 + x1) / 2, (y0 + y1) / 2, text=f"{completed_ratio * 100:.1f}%", fill=FG_PERCENT, font=("Segoe UI", 18 if scale >= 0.95 else 15, "bold"))
        legend_y = min(ch - 14, y1 + 16)
        c.create_rectangle(40, legend_y - 7, 54, legend_y + 7, fill=FG_SOMMA, outline="")
        c.create_text(110, legend_y, text="Completato", fill=FG, font=FONT_SMALL)
        c.create_rectangle(cw - 130, legend_y - 7, cw - 116, legend_y + 7, fill=FG_RESIDUO, outline="")
        c.create_text(cw - 60, legend_y, text="Residuo", fill=FG, font=FONT_SMALL)

    def _draw_bondo_evo_pie_chart(self, cap_pr: float, reached: float):
        """Disegna il grafico a torta per Bondora Evolution.

        Args:
            cap_pr: Cifra obiettivo (100%)
            reached: Cifra attualmente raggiunta
        """
        if self.bondo_evo_graph_canvas is None:
            return
        self._draw_pie_on_canvas(self.bondo_evo_graph_canvas, cap_pr, reached)

    def _draw_bondo_evo_next_days_pie_chart(self, total_days: float, completed_days: float):
        if self.bondo_evo_next_graph_canvas is None:
            return
        self._draw_pie_on_canvas(self.bondo_evo_next_graph_canvas, total_days, completed_days, size_scale=0.72)

    def _refresh_bondo_evo_display(self):
        """Aggiorna la visualizzazione dei dettagli per il valore selezionato."""
        if self.bondo_evo_info_frame is None:
            return

        selected_str = self.bondo_evo_daily_var.get().strip()
        for child in self.bondo_evo_info_frame.winfo_children():
            child.destroy()

        if not selected_str:
            return

        try:
            parsed_daily = self._parse_localized_number(selected_str)
            if parsed_daily is None:
                return
            daily_value = float(parsed_daily)
        except ValueError:
            return

        data = self.bondo_evo_data.get(daily_value)
        if not data:
            return

        if self._bondo_evo_redraw_job is not None:
            try:
                self.after_cancel(self._bondo_evo_redraw_job)
            except tk.TclError:
                pass
            self._bondo_evo_redraw_job = None

        cap_pr = float(data.get("cap_pr", 0.0) or 0.0)
        dtns = float(data.get("dtns", 0.0) or 0.0)
        mtns = float(data.get("mtns", 0.0) or 0.0)
        mdtns = data.get("mdtns")
        target_date = data.get("target_date")
        is_reached = bool(data.get("is_reached", False))

        # Calcola la Cifra Attuale dal primo obiettivo raggiunto
        current_amount = 0.0
        sorted_values = sorted(self.bondo_evo_data.keys())
        for val in sorted_values:
            prev_data = self.bondo_evo_data.get(val)
            if prev_data and bool(prev_data.get("is_reached", False)):
                # Primo obiettivo raggiunto trovato
                prev_cap_pr = float(prev_data.get("cap_pr", 0.0) or 0.0)
                prev_mtns = float(prev_data.get("mtns", 0.0) or 0.0)
                # Cifra Attuale = cap_pr + |mtns| (quando mtns è negativo, è esubero positivo)
                current_amount = prev_cap_pr + abs(prev_mtns)
                print(f"[DEBUG] Daily value: {daily_value}, Cap PR obiettivo raggiunto: {prev_cap_pr}, MTNS obiettivo raggiunto: {prev_mtns}, Cifra Attuale calcolata: {current_amount}")
                break

        # Disegna il grafico a torta
        # Se l'obiettivo è raggiunto, la cifra attuale deve essere al 100% dell'obiettivo
        self._draw_bondo_evo_pie_chart(cap_pr, current_amount)

        next_target = get_bondo_evo_next_unreached_target(self.bondo_evo_data)
        if next_target is None:
            self._draw_bondo_evo_next_days_pie_chart(1.0, 1.0)
            self.bondo_evo_next_info_var.set("Prossimo obiettivo: tutti raggiunti (100%)")
        else:
            next_daily, next_row = next_target
            if abs(float(next_daily) - float(daily_value)) < 1e-9:
                progress = get_bondo_evo_days_completion(
                    dtns=float(next_row.get("dtns", 0.0) or 0.0),
                    mdtns=next_row.get("mdtns"),
                )
                self._draw_bondo_evo_next_days_pie_chart(
                    progress["total_days"],
                    progress["completed_days"],
                )
                self.bondo_evo_next_info_var.set(
                    f"Prossimo obiettivo ({self._format_number_it(next_daily)} €/giorno): "
                    f"{progress['completed_ratio'] * 100:.1f}% "
                    f"({progress['completed_days']:.0f}/{progress['total_days']:.0f} giorni)"
                )
            else:
                if self.bondo_evo_next_graph_canvas is not None:
                    self.bondo_evo_next_graph_canvas.delete("all")
                self.bondo_evo_next_info_var.set("Grafico giorni visibile solo sul prossimo obiettivo.")

        tk.Label(
            self.bondo_evo_info_frame,
            text=f"Cifra obiettivo: {self._format_money_it(cap_pr)}\nGiorni effettivi obiettivo: {dtns:.0f} giorni",
            font=FONT_TABLE,
            bg=BG_TABLE,
            fg=FG,
            justify="left",
        ).pack(anchor="w", pady=(10, 0))

        if mtns < 0:
            mtns_color = FG_SOMMA
            mtns_text = f"Cifra mancante/esubero: {self._format_money_it(abs(mtns), prefix='EUR +')}"
        elif mtns > 0:
            mtns_color = FG_NEGATIVE
            mtns_text = f"Cifra mancante/esubero: {self._format_money_it(mtns, prefix='EUR -')}"
        else:
            mtns_color = FG
            mtns_text = "Cifra mancante/esubero: EUR 0.00"

        tk.Label(
            self.bondo_evo_info_frame,
            text=mtns_text,
            font=FONT_TABLE,
            bg=BG_TABLE,
            fg=mtns_color,
            justify="left",
        ).pack(anchor="w", pady=(5, 0))

        if is_reached:
            days_text = "Giorni all'obiettivo: RAGGIUNTO ✓"
            days_color = FG_SOMMA
        else:
            if mdtns is not None:
                days_text = f"Giorni all'obiettivo: {float(mdtns):.0f} giorni"
            else:
                days_text = "Giorni all'obiettivo: N/D"
            days_color = FG

        tk.Label(
            self.bondo_evo_info_frame,
            text=days_text,
            font=FONT_TABLE,
            bg=BG_TABLE,
            fg=days_color,
            justify="left",
        ).pack(anchor="w", pady=(5, 0))

        if not is_reached and target_date is not None:
            tk.Label(
                self.bondo_evo_info_frame,
                text=f"Giorno raggiungimento obiettivo: {target_date.strftime('%d/%m/%Y')}",
                font=FONT_TABLE,
                bg=BG_TABLE,
                fg=FG_HEADER,
                justify="left",
            ).pack(anchor="w", pady=(5, 0))



    # ── Confronto Mensile (GPP_ANNO) ────────────────────────────

    def _go_to_pv_window(self):
        if self.pv_window is not None and self.pv_window.winfo_exists():
            self.pv_window.deiconify()
            self.pv_window.lift()
            self.pv_window.focus_force()
            return

        self.pv_window = tk.Toplevel(self)
        self.pv_window.title("Own Finance - Previsionale")
        self.pv_window.geometry("760x260")
        self.pv_window.configure(bg=BG_TABLE)
        self.pv_window.minsize(720, 240)
        self.pv_window.protocol("WM_DELETE_WINDOW", self._close_pv_window)

        self._build_pv_window(self.pv_window)
        self._init_pv_filters()
        self._refresh_pv_selection()

    def _close_pv_window(self):
        if self.pv_window is not None and self.pv_window.winfo_exists():
            self.pv_window.destroy()
        self.pv_window = None
        self.pv_platform_cb = None
        self.pv_step_label = None
        self.pv_step_cb = None
        self.pv_targets_frame = None
        self.pv_active_detail_index = None
        self._refocus_main()

    def _build_pv_window(self, parent):
        wrapper = tk.Frame(parent, bg=BG_TABLE)
        wrapper.pack(fill="both", expand=True, padx=16, pady=16)

        header_row = tk.Frame(wrapper, bg=BG_TABLE)
        header_row.pack(fill="x")

        tk.Label(
            header_row,
            text="Previsionale",
            font=("Segoe UI", 12, "bold"),
            bg=BG_TABLE,
            fg=FG_HEADER,
        ).pack(side="left", anchor="w")

        tk.Button(
            header_row,
            text="← Torna indietro",
            bg=BG_FRAME,
            fg=FG,
            activebackground=SEL_BG,
            activeforeground=FG_HEADER,
            relief="flat",
            padx=10,
            command=self._close_pv_window,
        ).pack(side="right")

        controls = tk.Frame(wrapper, bg=BG_TABLE)
        controls.pack(fill="x", pady=(14, 0))

        tk.Label(controls, text="Piattaforma", font=FONT_SMALL, bg=BG_TABLE, fg=FG_HEADER).pack(side="left")
        self.pv_platform_cb = ttk.Combobox(
            controls,
            textvariable=self.pv_platform_var,
            state="readonly",
            width=16,
            values=[],
        )
        self.pv_platform_cb.pack(side="left", padx=(8, 0))
        self.pv_platform_cb.bind("<<ComboboxSelected>>", lambda _e: self._refresh_pv_selection())

        self.pv_step_label = tk.Label(controls, text="Step obiettivo", font=FONT_SMALL, bg=BG_TABLE, fg=FG_HEADER)
        self.pv_step_cb = ttk.Combobox(
            controls,
            textvariable=self.pv_step_var,
            state="readonly",
            width=10,
            values=[],
        )
        self.pv_step_cb.bind("<<ComboboxSelected>>", lambda _e: self._refresh_pv_selection())

        content = tk.Frame(wrapper, bg=BG_TABLE)
        content.pack(fill="both", expand=True, pady=(16, 0))

        tk.Label(
            content,
            textvariable=self.pv_title_var,
            font=("Segoe UI", 10, "bold"),
            bg=BG_TABLE,
            fg=FG_RESIDUO,
            justify="left",
        ).pack(anchor="w")

        tk.Label(
            content,
            textvariable=self.pv_result_var,
            font=("Segoe UI", 18, "bold"),
            bg=BG_TABLE,
            fg=FG_SOMMA,
            justify="left",
        ).pack(anchor="w", pady=(4, 0))

        self.pv_targets_frame = tk.Frame(content, bg=BG_TABLE)
        self.pv_targets_frame.pack(fill="x", pady=(8, 0))

        tk.Label(
            content,
            textvariable=self.pv_hint_var,
            font=FONT_SMALL,
            bg=BG_TABLE,
            fg=FG,
            justify="left",
        ).pack(anchor="w", pady=(8, 0))

    def _clear_pv_targets_rows(self):
        if self.pv_targets_frame is None:
            return
        for child in self.pv_targets_frame.winfo_children():
            child.destroy()

    def _render_pv_targets_rows(self, targets: list[dict[str, object]], step_value: float):
        self._clear_pv_targets_rows()
        if self.pv_targets_frame is None or not targets:
            return

        show_detail_toggle = abs(step_value - 10.0) < 1e-9

        if not show_detail_toggle:
            self.pv_active_detail_index = None
        elif self.pv_active_detail_index is not None and not (0 <= self.pv_active_detail_index < len(targets)):
            self.pv_active_detail_index = None

        tk.Label(
            self.pv_targets_frame,
            text=f"Obiettivi progressivi ({int(step_value)} €)",
            font=("Segoe UI", 9, "bold"),
            bg=BG_TABLE,
            fg=FG_HEADER,
        ).grid(row=0, column=0, sticky="w", padx=(0, 16), pady=(0, 4))

        grid_row = 1
        for idx, item in enumerate(targets):
            target_value = self._format_money_it(float(item.get("target", 0.0)))
            item_date = item.get("date")
            item_amount = item.get("amount")
            missing_days = item.get("missing_days")

            if isinstance(item_date, date) and isinstance(item_amount, float):
                left_text = (
                    f"{idx + 1}) {target_value} - {self._format_date_with_weekday_it(item_date)} "
                    f"(stima: {self._format_money_it(item_amount)})"
                )
            else:
                left_text = f"{idx + 1}) {target_value} - data non stimabile"

            row_frame = tk.Frame(self.pv_targets_frame, bg=BG_TABLE)
            row_frame.grid(row=grid_row, column=0, sticky="ew", pady=1)
            row_frame.grid_columnconfigure(0, weight=1)
            grid_row += 1

            left_block = tk.Frame(row_frame, bg=BG_TABLE)
            left_block.grid(row=0, column=0, sticky="w")

            tk.Label(
                left_block,
                text=left_text,
                font=FONT_SMALL,
                bg=BG_TABLE,
                fg=FG,
                justify="left",
            ).pack(side="left")

            tk.Label(
                left_block,
                text="    Giorni mancanti: ",
                font=FONT_SMALL,
                bg=BG_TABLE,
                fg=FG,
            ).pack(side="left")

            days_text = str(int(missing_days)) if isinstance(missing_days, (int, float)) else "N/D"
            tk.Label(
                left_block,
                text=days_text,
                font=("Segoe UI", 9, "bold"),
                bg=BG_TABLE,
                fg=FG_NEGATIVE,
            ).pack(side="left")

            if show_detail_toggle:
                is_on = self.pv_active_detail_index == idx
                switch = self._create_pv_detail_switch(
                    row_frame,
                    is_on=is_on,
                    on_toggle=lambda i=idx, state=(not is_on): self._toggle_pv_detail(i, state),
                )
                switch.grid(row=0, column=1, padx=(12, 0), sticky="e")

                if self.pv_active_detail_index == idx:
                    detail_rows = item.get("euro_details") or []

                    # Calcola le soglie cap_pr (cifre che aumentano il guadagno giornaliero di 1 centesimo)
                    cap_pr_milestones: set[int] = set()
                    for bondo_row in self.bondo_evo_data.values():
                        cp = bondo_row.get("cap_pr")
                        if cp is not None:
                            try:
                                cp_val = float(cp)
                                if cp_val > 0:
                                    cap_pr_milestones.add(math.ceil(cp_val))
                            except (ValueError, TypeError):
                                pass

                    detail_frame = tk.Frame(self.pv_targets_frame, bg=BG_TABLE)
                    detail_frame.grid(row=grid_row, column=0, sticky="ew", padx=(18, 0), pady=(0, 4))
                    grid_row += 1

                    if not detail_rows:
                        tk.Label(
                            detail_frame,
                            text="Dettaglio non disponibile.",
                            font=FONT_SMALL,
                            bg=BG_TABLE,
                            fg=FG_HEADER,
                            justify="left",
                        ).pack(anchor="w")
                    else:
                        for detail_idx, detail in enumerate(detail_rows, start=1):
                            euro_target = float(detail.get("target", 0.0))
                            euro_date = detail.get("date")
                            euro_amount = detail.get("amount")
                            euro_missing_days = detail.get("missing_days")
                            euro_days_text = (
                                f" - Giorni mancanti: {int(euro_missing_days)}"
                                if isinstance(euro_missing_days, (int, float))
                                else " - Giorni mancanti: N/D"
                            )
                            if isinstance(euro_date, date) and isinstance(euro_amount, float):
                                line_text = (
                                    f"{detail_idx}) {self._format_money_it(euro_target)}: "
                                    f"{self._format_date_with_weekday_it(euro_date)} "
                                    f"(stima: {self._format_money_it(euro_amount)}){euro_days_text}"
                                )
                            else:
                                line_text = (
                                    f"{detail_idx}) {self._format_money_it(euro_target)}: "
                                    f"data non stimabile{euro_days_text}"
                                )

                            # Evidenzia in verde le soglie che aumentano il guadagno giornaliero
                            is_milestone = int(euro_target) in cap_pr_milestones
                            line_color = FG_SOMMA if is_milestone else FG_HEADER

                            row_lbl = tk.Label(
                                detail_frame,
                                text=line_text,
                                font=("Segoe UI", 9, "bold") if is_milestone else FONT_SMALL,
                                bg=BG_TABLE,
                                fg=line_color,
                                justify="left",
                            )
                            row_lbl.pack(anchor="w")

    def _toggle_pv_detail(self, row_index: int, enabled: bool):
        if enabled:
            self.pv_active_detail_index = row_index
        elif self.pv_active_detail_index == row_index:
            self.pv_active_detail_index = None
        self._refresh_pv_selection()

    def _create_pv_detail_switch(self, parent, *, is_on: bool, on_toggle):
        """Crea un toggle switch grafico (non checkbox) per il dettaglio riga."""
        holder = tk.Frame(parent, bg=BG_TABLE)
        tk.Label(
            holder,
            text="Dettaglio",
            font=FONT_SMALL,
            bg=BG_TABLE,
            fg=FG,
        ).pack(side="left", padx=(0, 6))

        width, height = 40, 22
        radius = 10
        knob_d = 16
        off_bg = "#4b5563"
        on_bg = "#22c55e"
        knob_color = "#f8fafc"

        canvas = tk.Canvas(
            holder,
            width=width,
            height=height,
            bg=BG_TABLE,
            highlightthickness=0,
            bd=0,
            relief="flat",
            cursor="hand2",
        )
        canvas.pack(side="left")

        fill_color = on_bg if is_on else off_bg
        # Corpo pill (rettangolo + 2 estremita' arrotondate)
        canvas.create_rectangle(radius, 1, width - radius, height - 1, fill=fill_color, outline=fill_color)
        canvas.create_oval(1, 1, radius * 2, height - 1, fill=fill_color, outline=fill_color)
        canvas.create_oval(width - radius * 2, 1, width - 1, height - 1, fill=fill_color, outline=fill_color)

        knob_x = width - knob_d - 3 if is_on else 3
        canvas.create_oval(knob_x, 3, knob_x + knob_d, 3 + knob_d, fill=knob_color, outline=knob_color)

        canvas.bind("<Button-1>", lambda _e: on_toggle())
        return holder

    def _init_pv_filters(self):
        values = ["Bondora", "Mintos", "Tutte"]
        if self.pv_platform_cb is not None:
            self.pv_platform_cb["values"] = values
        if self.pv_step_cb is not None:
            self.pv_step_cb["values"] = ["10 €", "25 €", "50 €", "100 €", "500 €", "1000 €"]
        if not self.pv_platform_var.get():
            self.pv_platform_var.set("Tutte")
        if not self.pv_step_var.get():
            self.pv_step_var.set("10 €")

    def _get_pv_step_amount(self) -> float:
        raw = self.pv_step_var.get().replace("€", "").strip()
        value = self._parse_localized_number(raw)
        if value is None or value <= 0:
            return 10.0
        return float(value)

    def _calculate_bondora_progressive_targets(self, step: float, count: int = 5) -> list[dict[str, object]]:
        """Calcola data e cifra stimata al raggiungimento dei prossimi target Bondora."""
        current_amount, current_daily_rate = self._get_bondora_current_snapshot()
        targets = get_progressive_amount_targets(current_amount, step, count)
        if not targets or current_daily_rate <= 0:
            return []

        today = date.today()
        amount = float(current_amount)
        daily_rate = float(current_daily_rate)

        euro_targets = get_euro_milestone_targets(current_amount, max(targets))
        euro_hits: list[dict[str, object]] = []

        events: list[tuple[date, float]] = []
        for daily, row in self.bondo_evo_data.items():
            if bool(row.get("is_reached", False)):
                continue
            target_date = row.get("target_date")
            if isinstance(target_date, date) and target_date > today:
                events.append((target_date, float(daily)))
        events.sort(key=lambda x: (x[0], x[1]))

        output: list[dict[str, object]] = []
        next_idx = 0
        next_euro_idx = 0
        event_idx = 0
        current_day = today
        prev_row_target = float(current_amount)

        max_sim_days = 36500  # margine ampio per trovare i target anche in scenari molto conservativi
        for _ in range(max_sim_days):
            current_day = current_day + timedelta(days=1)
            while event_idx < len(events) and events[event_idx][0] <= current_day:
                daily_rate = max(daily_rate, events[event_idx][1])
                event_idx += 1

            amount += daily_rate

            while next_euro_idx < len(euro_targets) and amount >= euro_targets[next_euro_idx]:
                euro_hits.append(
                    {
                        "target": euro_targets[next_euro_idx],
                        "date": current_day,
                        "amount": amount,
                        "missing_days": (current_day - today).days,
                    }
                )
                next_euro_idx += 1

            while next_idx < len(targets) and amount >= targets[next_idx]:
                row_target = targets[next_idx]
                output.append(
                    {
                        "target": row_target,
                        "date": current_day,
                        "amount": amount,
                        "missing_days": (current_day - today).days,
                        "euro_details": [
                            hit
                            for hit in euro_hits
                            if prev_row_target < float(hit.get("target", 0.0)) <= float(row_target)
                        ],
                    }
                )
                prev_row_target = float(row_target)
                next_idx += 1

            if next_idx >= len(targets):
                break

        while next_idx < len(targets):
            output.append(
                {
                    "target": targets[next_idx],
                    "date": None,
                    "amount": None,
                    "missing_days": None,
                    "euro_details": [],
                }
            )
            next_idx += 1

        return output

    def _get_bondora_current_snapshot(self) -> tuple[float, float]:
        """Restituisce (cifra_attuale, daily_rate_attuale) usando i dati Bondora Evolution."""
        if not self.bondo_evo_data:
            return 0.0, 0.0

        reached_entries = [
            (float(daily), row)
            for daily, row in self.bondo_evo_data.items()
            if bool(row.get("is_reached", False))
        ]

        if reached_entries:
            daily_rate, row = max(
                reached_entries,
                key=lambda item: float(item[1].get("cap_pr", 0.0) or 0.0),
            )
            cap_pr = float(row.get("cap_pr", 0.0) or 0.0)
            mtns = float(row.get("mtns", 0.0) or 0.0)
            current_amount = max(0.0, cap_pr + abs(mtns))
            return current_amount, daily_rate

        # Fallback: usa il primo target disponibile.
        first_daily = float(sorted(self.bondo_evo_data.keys())[0])
        row = self.bondo_evo_data.get(first_daily, {})
        cap_pr = float(row.get("cap_pr", 0.0) or 0.0)
        mtns = float(row.get("mtns", 0.0) or 0.0)
        current_amount = max(0.0, cap_pr - mtns)
        return current_amount, first_daily

    def _calculate_bondora_forecast(self) -> tuple[float, float, float, str]:
        """Proietta la cifra Bondora a fine anno usando le soglie/target date di Bondora Evolution."""
        if not self.bondo_evo_data:
            return 0.0, 0.0, 0.0, "Dati Bondora Evolution non disponibili."

        today = date.today()
        end_year = date(today.year, 12, 31)

        current_amount, daily_rate = self._get_bondora_current_snapshot()
        if current_amount <= 0.0 and daily_rate <= 0.0:
            return 0.0, 0.0, 0.0, "Dati Bondora non sufficienti per la previsione."

        current_daily_rate = daily_rate

        forecast = current_amount

        events: list[tuple[date, float]] = []
        for daily, row in self.bondo_evo_data.items():
            if bool(row.get("is_reached", False)):
                continue
            target_date = row.get("target_date")
            if isinstance(target_date, date) and today < target_date <= end_year:
                events.append((target_date, float(daily)))
        events.sort(key=lambda x: (x[0], x[1]))

        event_idx = 0
        for day_ord in range((today + timedelta(days=1)).toordinal(), end_year.toordinal() + 1):
            current_day = date.fromordinal(day_ord)
            while event_idx < len(events) and events[event_idx][0] <= current_day:
                # La daily può solo aumentare al raggiungimento di uno step successivo.
                daily_rate = max(daily_rate, events[event_idx][1])
                event_idx += 1
            forecast += daily_rate

        projected_gain = max(0.0, forecast - current_amount)
        hint = (
            f"Guadagno giornaliero attuale: {self._format_money_it(current_daily_rate, prefix='EUR/giorno')}\n"
            f"Guadagno giornaliero previsionale: {self._format_money_it(daily_rate, prefix='EUR/giorno')}\n"
            f"Guadagno previsionale anno: {self._format_money_it(current_amount)} + "
            f"{self._format_money_it(projected_gain)} = {self._format_money_it(forecast)}"
        )
        return forecast, current_amount, projected_gain, hint

    def _calculate_mintos_forecast(self) -> tuple[float, float, float, str]:
        """Stima Mintos a fine anno da media mensile attuale (media * 12)."""
        if not isinstance(self.gpp_data, dict) or not self.gpp_data:
            return 0.0, 0.0, 0.0, "Dati GPP_ANNO non disponibili."

        current_year = str(datetime.now().year)
        years = [str(y) for y in self.gpp_data.get("years", [])]
        if current_year not in years:
            return 0.0, 0.0, 0.0, f"Anno {current_year} non disponibile in GPP_ANNO."

        month_num = datetime.now().month
        month_display = f"{month_num}. {MESI[month_num - 1].capitalize()}"
        # Quota attuale: valore piattaforma in INV+GUAD (mese corrente, fallback ultimo disponibile).
        current_cumulative = self._get_current_platform_amount("Mintos")
        # Fallback: se INV+GUAD non è disponibile, usa cumulato guadagni da GPP_ANNO.
        if current_cumulative <= 0.0:
            current_cumulative = self._gpp_cumulative_value("Mintos", current_year, month_display)
        monthly_avg = self._mm_calculate_average("Mintos", current_year, month_display)
        months_remaining = max(0, 12 - month_num)
        projected_gain = max(0.0, monthly_avg * months_remaining)
        forecast = max(0.0, current_cumulative + projected_gain)
        hint = (
            f"Quota attuale Mintos (INV+GUAD): {self._format_money_it(current_cumulative)}\n"
            f"Media mensile attuale Mintos: {self._format_money_it(monthly_avg)}\n"
            f"Guadagno previsionale anno: {self._format_money_it(current_cumulative)} + "
            f"{self._format_money_it(projected_gain)} = {self._format_money_it(forecast)}"
        )
        return forecast, current_cumulative, projected_gain, hint

    def _refresh_pv_selection(self):
        platform = self.pv_platform_var.get().strip()
        if not platform:
            self._clear_pv_targets_rows()
            self.pv_title_var.set("")
            self.pv_result_var.set("Seleziona una piattaforma")
            self.pv_hint_var.set("")
            self.pv_active_detail_index = None
            return

        if self.pv_step_label is not None and self.pv_step_cb is not None:
            if platform == "Bondora":
                if not self.pv_step_label.winfo_ismapped():
                    self.pv_step_label.pack(side="left", padx=(18, 0))
                if not self.pv_step_cb.winfo_ismapped():
                    self.pv_step_cb.pack(side="left", padx=(8, 0))
            else:
                if self.pv_step_label.winfo_ismapped():
                    self.pv_step_label.pack_forget()
                if self.pv_step_cb.winfo_ismapped():
                    self.pv_step_cb.pack_forget()

        bondora_forecast, bondora_current, bondora_projected, bondora_hint = self._calculate_bondora_forecast()
        mintos_forecast, mintos_current, mintos_projected, mintos_hint = self._calculate_mintos_forecast()
        year = datetime.now().year

        if platform == "Bondora":
            self.pv_title_var.set(f"Previsionale Bondora a fine {year}")
            self.pv_result_var.set(self._format_money_it(bondora_forecast))
            step_value = self._get_pv_step_amount()
            if abs(step_value - 10.0) >= 1e-9:
                self.pv_active_detail_index = None
            targets = self._calculate_bondora_progressive_targets(step_value, count=5)
            self._render_pv_targets_rows(targets, step_value)

            if targets:
                first = targets[0]
                first_date = first.get("date")
                first_amount = first.get("amount")
                if isinstance(first_date, date) and isinstance(first_amount, float):
                    next_line = (
                        f"Prossimo target ({int(step_value)} €): {self._format_money_it(float(first['target']))} - "
                        f"{first_date.strftime('%d/%m/%Y')} (stima: {self._format_money_it(first_amount)})"
                    )
                else:
                    next_line = (
                        f"Prossimo target ({int(step_value)} €): {self._format_money_it(float(first['target']))} - "
                        "data non stimabile"
                    )

                upcoming_lines = []
                for idx, item in enumerate(targets[:4], start=1):
                    target_value = self._format_money_it(float(item["target"]))
                    item_date = item.get("date")
                    item_amount = item.get("amount")
                    if isinstance(item_date, date) and isinstance(item_amount, float):
                        upcoming_lines.append(
                            f"{idx}) {target_value} - {item_date.strftime('%d/%m/%Y')} (stima: {self._format_money_it(item_amount)})"
                        )
                    else:
                        upcoming_lines.append(f"{idx}) {target_value} - data non stimabile")

                targets_hint = (
                    f"{next_line}\n"
                    f"Previsionale prossimi 4 obiettivi:\n" + "\n".join(upcoming_lines)
                )
                self.pv_hint_var.set(bondora_hint)
            else:
                self.pv_hint_var.set(bondora_hint)
        elif platform == "Mintos":
            self.pv_active_detail_index = None
            self._clear_pv_targets_rows()
            self.pv_title_var.set(f"Previsionale Mintos a fine {year}")
            self.pv_result_var.set(self._format_money_it(mintos_forecast))
            self.pv_hint_var.set(
                f"Totale atteso fine anno Mintos: {self._format_money_it(mintos_forecast)}\n"
                f"{mintos_hint}"
            )
        else:
            self.pv_active_detail_index = None
            self._clear_pv_targets_rows()
            total = bondora_forecast + mintos_forecast
            total_current = bondora_current + mintos_current
            total_projected = bondora_projected + mintos_projected
            self.pv_title_var.set(f"Previsionale Totale (Bondora + Mintos) a fine {year}")
            self.pv_result_var.set(self._format_money_it(total))
            self.pv_hint_var.set(
                f"Bondora: {self._format_money_it(bondora_forecast)} | Mintos: {self._format_money_it(mintos_forecast)}\n"
                f"Guadagno previsionale anno: {self._format_money_it(total_current)} + "
                f"{self._format_money_it(total_projected)} = {self._format_money_it(total)}"
            )

    def _go_to_bmb_window(self):
        if self.bmb_window is not None and self.bmb_window.winfo_exists():
            self.bmb_window.deiconify()
            self.bmb_window.lift()
            self.bmb_window.focus_force()
            self._render_bmb_table()
            return

        self.bmb_window = tk.Toplevel(self)
        self.bmb_window.title("Own Finance - Previsionale mensile Bondora")
        self.bmb_window.geometry("1480x560")
        self.bmb_window.configure(bg=BG_TABLE)
        self.bmb_window.minsize(1100, 420)
        self.bmb_window.protocol("WM_DELETE_WINDOW", self._close_bmb_window)

        self._build_bmb_window(self.bmb_window)
        self._render_bmb_table()

    def _go_to_icb_window(self):
        if self.icb_window is not None and self.icb_window.winfo_exists():
            self.icb_window.deiconify()
            self.icb_window.lift()
            self.icb_window.focus_force()
            self._render_icb_table()
            return

        self.icb_window = tk.Toplevel(self)
        self.icb_window.title("Own Finance - Interesse composto Bondora")
        self.icb_window.geometry("1320x360")
        self.icb_window.configure(bg=BG_TABLE)
        self.icb_window.minsize(900, 280)
        self.icb_window.protocol("WM_DELETE_WINDOW", self._close_icb_window)

        self._build_icb_window(self.icb_window)
        self._render_icb_table()

    def _close_icb_window(self):
        if self.icb_window is not None and self.icb_window.winfo_exists():
            self.icb_window.destroy()
        self.icb_window = None
        self.icb_table_canvas = None
        self.icb_table_body = None
        self._refocus_main()

    def _build_icb_window(self, parent: tk.Toplevel):
        wrapper = tk.Frame(parent, bg=BG_TABLE)
        wrapper.pack(fill="both", expand=True, padx=16, pady=16)

        header_row = tk.Frame(wrapper, bg=BG_TABLE)
        header_row.pack(fill="x")

        tk.Label(
            header_row,
            text="Interesse composto Bondora",
            font=("Segoe UI", 12, "bold"),
            bg=BG_TABLE,
            fg=FG_HEADER,
        ).pack(side="left", anchor="w")

        tk.Button(
            header_row,
            text="← Torna indietro",
            bg=BG_FRAME,
            fg=FG,
            activebackground=SEL_BG,
            activeforeground=FG_HEADER,
            relief="flat",
            padx=10,
            command=self._close_icb_window,
        ).pack(side="right")

        tk.Label(
            wrapper,
            textvariable=self.icb_hint_var,
            font=FONT_SMALL,
            bg=BG_TABLE,
            fg=FG,
            justify="left",
        ).pack(anchor="w", pady=(10, 8))

        table_wrapper = tk.Frame(wrapper, bg=BG_TABLE)
        table_wrapper.pack(fill="both", expand=True)

        self.icb_table_canvas = tk.Canvas(table_wrapper, bg=BG_TABLE, highlightthickness=0)
        vsb = ttk.Scrollbar(table_wrapper, orient="vertical", command=self.icb_table_canvas.yview)
        hsb = ttk.Scrollbar(table_wrapper, orient="horizontal", command=self.icb_table_canvas.xview)
        self.icb_table_canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        self.icb_table_canvas.pack(side="left", fill="both", expand=True)

        self.icb_table_body = tk.Frame(self.icb_table_canvas, bg=BG_TABLE)
        window_id = self.icb_table_canvas.create_window((0, 0), window=self.icb_table_body, anchor="nw")

        def _refresh_scrollregion(_event=None):
            if self.icb_table_canvas is not None:
                self.icb_table_canvas.configure(scrollregion=self.icb_table_canvas.bbox("all"))

        def _sync_width(event):
            if self.icb_table_canvas is None or self.icb_table_body is None:
                return
            requested = self.icb_table_body.winfo_reqwidth()
            self.icb_table_canvas.itemconfigure(window_id, width=max(event.width, requested))

        self.icb_table_body.bind("<Configure>", _refresh_scrollregion)
        self.icb_table_canvas.bind("<Configure>", _sync_width)

    def _calculate_bondora_compound_yearly_to_2050(self) -> dict[int, float]:
        today = date.today()
        if today.year > 2050:
            return {}

        current_amount, daily_rate = self._get_bondora_current_snapshot()
        if current_amount <= 0.0 and daily_rate <= 0.0:
            return {}

        milestones: list[tuple[float, float]] = []
        for daily, row in self.bondo_evo_data.items():
            cap_pr = row.get("cap_pr")
            try:
                cap_pr_value = float(cap_pr)
                daily_value = float(daily)
            except (TypeError, ValueError):
                continue
            if cap_pr_value <= 0.0 or daily_value <= 0.0:
                continue
            milestones.append((cap_pr_value, daily_value))
        milestones.sort(key=lambda item: item[0])

        simulated_amount = current_amount
        milestone_idx = 0
        while milestone_idx < len(milestones) and simulated_amount + 1e-9 >= milestones[milestone_idx][0]:
            daily_rate = max(daily_rate, milestones[milestone_idx][1])
            milestone_idx += 1

        yearly_data: dict[int, float] = {}
        cursor = today
        for year in range(today.year, 2051):
            year_end = date(year, 12, 31)
            for day_ord in range((cursor + timedelta(days=1)).toordinal(), year_end.toordinal() + 1):
                while milestone_idx < len(milestones) and simulated_amount + 1e-9 >= milestones[milestone_idx][0]:
                    daily_rate = max(daily_rate, milestones[milestone_idx][1])
                    milestone_idx += 1
                simulated_amount += daily_rate
            yearly_data[year] = simulated_amount
            cursor = year_end

        return yearly_data

    def _render_icb_table(self):
        if self.icb_table_body is None or self.icb_table_canvas is None:
            return

        for child in self.icb_table_body.winfo_children():
            child.destroy()

        yearly_data = self._calculate_bondora_compound_yearly_to_2050()
        self.icb_yearly_data = yearly_data

        if not yearly_data:
            self.icb_hint_var.set("Dati Bondora non sufficienti per il calcolo dell'interesse composto.")
            tk.Label(
                self.icb_table_body,
                text="Nessun dato disponibile.",
                bg=BG_TABLE,
                fg=FG_ACCENT,
                font=FONT_TABLE,
            ).pack(anchor="w", padx=10, pady=10)
            return

        start_amount, start_daily = self._get_bondora_current_snapshot()
        self.icb_hint_var.set(
            "Capitale calcolato partendo dalla cifra Bondora attuale e simulando la crescita giornaliera. "
            "Orizzonte: fino al 2050. "
            f"Base attuale: {self._format_money_it(start_amount)} | Daily corrente: "
            f"{self._format_money_it(start_daily, prefix='EUR/giorno')}"
        )

        years = sorted(yearly_data.keys())
        chunk_size = 10
        year_chunks = [years[i:i + chunk_size] for i in range(0, len(years), chunk_size)]
        total_rows = max((len(chunk) for chunk in year_chunks), default=0)

        for block_idx, chunk in enumerate(year_chunks):
            base_col = block_idx * 2
            anno_col = base_col
            cap_col = base_col + 1

            self.icb_table_body.grid_columnconfigure(anno_col, minsize=90, weight=0)
            self.icb_table_body.grid_columnconfigure(cap_col, minsize=170, weight=0)

            tk.Label(
                self.icb_table_body,
                text="Anno",
                font=FONT_TAB,
                bg=BG_FRAME,
                fg=FG_HEADER,
                padx=10,
                pady=8,
                anchor="center",
                highlightthickness=1,
                highlightbackground=BG,
            ).grid(row=0, column=anno_col, sticky="nsew")

            tk.Label(
                self.icb_table_body,
                text="Capitale atteso",
                font=FONT_TAB,
                bg=BG_FRAME,
                fg=FG_HEADER,
                padx=10,
                pady=8,
                anchor="center",
                highlightthickness=1,
                highlightbackground=BG,
            ).grid(row=0, column=cap_col, sticky="nsew")

            for row_idx in range(1, total_rows + 1):
                has_data = row_idx <= len(chunk)
                year_value = chunk[row_idx - 1] if has_data else ""
                capital_value = (
                    self._format_number_it(float(yearly_data.get(int(year_value), 0.0)), 2)
                    if has_data else ""
                )

                tk.Label(
                    self.icb_table_body,
                    text=str(year_value),
                    font=("Segoe UI", 10, "bold") if has_data else FONT_TABLE,
                    bg=BG_TABLE,
                    fg=FG_HEADER if has_data else FG,
                    padx=10,
                    pady=7,
                    anchor="center",
                    highlightthickness=1,
                    highlightbackground=BG,
                ).grid(row=row_idx, column=anno_col, sticky="nsew")

                tk.Label(
                    self.icb_table_body,
                    text=capital_value,
                    font=("Segoe UI", 10, "bold") if has_data else FONT_TABLE,
                    bg=BG_TABLE,
                    fg=FG_SOMMA if has_data else FG,
                    padx=10,
                    pady=7,
                    anchor="center",
                    highlightthickness=1,
                    highlightbackground=BG,
                ).grid(row=row_idx, column=cap_col, sticky="nsew")

        self.icb_table_body.update_idletasks()
        self.icb_table_canvas.configure(scrollregion=self.icb_table_canvas.bbox("all"))

    def _close_bmb_window(self):
        if self.bmb_window is not None and self.bmb_window.winfo_exists():
            self.bmb_window.destroy()
        self.bmb_window = None
        self.bmb_table_canvas = None
        self.bmb_table_body = None
        self._refocus_main()

    def _build_bmb_window(self, parent: tk.Toplevel):
        wrapper = tk.Frame(parent, bg=BG_TABLE)
        wrapper.pack(fill="both", expand=True, padx=16, pady=16)

        header_row = tk.Frame(wrapper, bg=BG_TABLE)
        header_row.pack(fill="x")

        tk.Label(
            header_row,
            text="Previsionale mensile Bondora",
            font=("Segoe UI", 12, "bold"),
            bg=BG_TABLE,
            fg=FG_HEADER,
        ).pack(side="left", anchor="w")

        tk.Button(
            header_row,
            text="← Torna indietro",
            bg=BG_FRAME,
            fg=FG,
            activebackground=SEL_BG,
            activeforeground=FG_HEADER,
            relief="flat",
            padx=10,
            command=self._close_bmb_window,
        ).pack(side="right")

        tk.Label(
            wrapper,
            textvariable=self.bmb_hint_var,
            font=FONT_SMALL,
            bg=BG_TABLE,
            fg=FG,
            justify="left",
        ).pack(anchor="w", pady=(10, 8))

        table_wrapper = tk.Frame(wrapper, bg=BG_TABLE)
        table_wrapper.pack(fill="both", expand=True)

        self.bmb_table_canvas = tk.Canvas(table_wrapper, bg=BG_TABLE, highlightthickness=0)
        vsb = ttk.Scrollbar(table_wrapper, orient="vertical", command=self.bmb_table_canvas.yview)
        hsb = ttk.Scrollbar(table_wrapper, orient="horizontal", command=self.bmb_table_canvas.xview)
        self.bmb_table_canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        self.bmb_table_canvas.pack(side="left", fill="both", expand=True)

        self.bmb_table_body = tk.Frame(self.bmb_table_canvas, bg=BG_TABLE)
        window_id = self.bmb_table_canvas.create_window((0, 0), window=self.bmb_table_body, anchor="nw")

        def _refresh_scrollregion(_event=None):
            if self.bmb_table_canvas is not None:
                self.bmb_table_canvas.configure(scrollregion=self.bmb_table_canvas.bbox("all"))

        def _sync_width(event):
            if self.bmb_table_canvas is None or self.bmb_table_body is None:
                return
            requested = self.bmb_table_body.winfo_reqwidth()
            self.bmb_table_canvas.itemconfigure(window_id, width=max(event.width, requested))

        self.bmb_table_body.bind("<Configure>", _refresh_scrollregion)
        self.bmb_table_canvas.bind("<Configure>", _sync_width)

    def _get_ctm_bondora_monthly_values_for_year(self, year: str) -> dict[str, float]:
        values = {month: 0.0 for month in MESI}
        if not isinstance(self.ctm_data, dict):
            return values

        rows = self.ctm_data.get("rows", [])
        if not isinstance(rows, list):
            return values

        for row in rows:
            if str(row.get("year", "")).strip() != str(year):
                continue
            details = row.get("details", {}) if isinstance(row.get("details", {}), dict) else {}
            for month in MESI:
                month_details = details.get(month, {}) if isinstance(details.get(month, {}), dict) else {}
                values[month] = float(month_details.get("Bondora", 0.0) or 0.0)
            break
        return values

    def _calculate_bondora_monthly_forecast_rows(
        self,
        horizon_years: int = 10,
    ) -> tuple[list[dict[str, object]], dict[tuple[int, int], dict[str, object]]]:
        today = date.today()
        start_year = today.year
        end_year = start_year + horizon_years

        current_amount, daily_rate = self._get_bondora_current_snapshot()
        snapshot_amount = current_amount
        simulated_amount = current_amount

        monthly_projected: dict[tuple[int, int], float] = {
            (year, month): 0.0
            for year in range(start_year, end_year + 1)
            for month in range(1, 13)
        }

        milestones: list[tuple[float, float]] = []
        for daily, row in self.bondo_evo_data.items():
            cap_pr = row.get("cap_pr")
            try:
                cap_pr_value = float(cap_pr)
                daily_value = float(daily)
            except (TypeError, ValueError):
                continue
            if cap_pr_value <= 0.0 or daily_value <= 0.0:
                continue
            milestones.append((cap_pr_value, daily_value))
        milestones.sort(key=lambda item: item[0])

        milestone_idx = 0
        while milestone_idx < len(milestones) and simulated_amount + 1e-9 >= milestones[milestone_idx][0]:
            daily_rate = max(daily_rate, milestones[milestone_idx][1])
            milestone_idx += 1

        end_date = date(end_year, 12, 31)
        for day_ord in range((today + timedelta(days=1)).toordinal(), end_date.toordinal() + 1):
            while milestone_idx < len(milestones) and simulated_amount + 1e-9 >= milestones[milestone_idx][0]:
                daily_rate = max(daily_rate, milestones[milestone_idx][1])
                milestone_idx += 1

            current_day = date.fromordinal(day_ord)
            simulated_amount += daily_rate
            key = (current_day.year, current_day.month)
            if key in monthly_projected:
                monthly_projected[key] += daily_rate

        current_year_actual = self._get_ctm_bondora_monthly_values_for_year(str(start_year))

        # Saldo di riferimento: cifra attuale Bondora. Da qui sommiamo i mesi previsionali.
        forecast_balance_cursor = snapshot_amount

        rows: list[dict[str, object]] = []
        month_details: dict[tuple[int, int], dict[str, object]] = {}
        for year in range(start_year, end_year + 1):
            monthly_values: dict[str, float] = {}
            for month_idx, month_name in enumerate(MESI, start=1):
                projected_value = float(monthly_projected.get((year, month_idx), 0.0))
                actual_value = 0.0
                source = "forecast"

                if year == start_year:
                    actual_value = float(current_year_actual.get(month_name, 0.0) or 0.0)
                    if month_idx < today.month:
                        value = actual_value
                        source = "actual"
                    elif month_idx == today.month:
                        value = actual_value + projected_value
                        source = "actual+forecast" if actual_value > 0.0 else "forecast"
                    else:
                        value = projected_value
                else:
                    value = projected_value

                projection_available = year > start_year or (year == start_year and month_idx >= today.month)
                projected_for_balance = projected_value if projection_available else 0.0

                month_start = None
                month_end = None
                if projection_available:
                    month_start = forecast_balance_cursor
                    month_end = month_start + projected_for_balance
                    forecast_balance_cursor = month_end

                monthly_values[month_name] = value
                month_details[(year, month_idx)] = {
                    "year": year,
                    "month_idx": month_idx,
                    "month_name": month_name,
                    "gain": value,
                    "actual_gain": actual_value,
                    "projected_gain": projected_value,
                    "projected_gain_used": projected_for_balance,
                    "start_balance": month_start,
                    "end_balance": month_end,
                    "projection_available": projection_available,
                    "source": source,
                }

            annual_total = sum(monthly_values.values())
            rows.append({"year": year, "monthly": monthly_values, "annual_total": annual_total})

        return rows, month_details

    def _render_bmb_table(self):
        if self.bmb_table_body is None or self.bmb_table_canvas is None:
            return

        for child in self.bmb_table_body.winfo_children():
            child.destroy()

        rows, month_details = self._calculate_bondora_monthly_forecast_rows(horizon_years=10)
        today = date.today()
        self.bmb_monthly_data = month_details

        if not rows:
            self.bmb_hint_var.set("Nessun dato disponibile per il previsionale mensile Bondora.")
            tk.Label(
                self.bmb_table_body,
                text="Nessun dato disponibile.",
                bg=BG_TABLE,
                fg=FG_ACCENT,
                font=FONT_TABLE,
            ).pack(anchor="w", padx=10, pady=10)
            return

        self.bmb_hint_var.set(
            "Mesi gia trascorsi dell'anno corrente evidenziati in verde. "
            "Previsione calcolata assumendo nessun nuovo versamento. "
            "Passa con il mouse su un valore mensile per visualizzare il saldo atteso a fine mese."
        )

        cols = ["Anno"] + [month.capitalize() for month in MESI] + ["Totale"]
        for col_idx, col_name in enumerate(cols):
            width = 90 if col_name == "Anno" else (120 if col_name == "Totale" else 96)
            self.bmb_table_body.grid_columnconfigure(col_idx, minsize=width, weight=0)
            tk.Label(
                self.bmb_table_body,
                text=col_name,
                font=FONT_TAB,
                bg=BG_FRAME,
                fg=FG_HEADER,
                padx=10,
                pady=8,
                anchor="center",
                highlightthickness=1,
                highlightbackground=BG,
            ).grid(row=0, column=col_idx, sticky="nsew")

        past_month_bg = "#355d45"
        for row_idx, row in enumerate(rows, start=1):
            year_value = int(row.get("year", 0) or 0)
            monthly = row.get("monthly", {}) if isinstance(row.get("monthly", {}), dict) else {}
            annual_total = float(row.get("annual_total", 0.0) or 0.0)

            tk.Label(
                self.bmb_table_body,
                text=str(year_value),
                font=("Segoe UI", 10, "bold"),
                bg=BG_TABLE,
                fg=FG_HEADER,
                padx=10,
                pady=6,
                anchor="center",
                highlightthickness=1,
                highlightbackground=BG,
            ).grid(row=row_idx, column=0, sticky="nsew")

            for month_idx, month_name in enumerate(MESI, start=1):
                month_value = float(monthly.get(month_name, 0.0) or 0.0)
                is_past_current_year = year_value == today.year and month_idx < today.month
                cell_bg = past_month_bg if is_past_current_year else BG_TABLE
                cell_fg = FG_SOMMA if month_value > 0 else FG

                month_label = tk.Label(
                    self.bmb_table_body,
                    text=self._format_number_it(month_value, 2),
                    font=FONT_SMALL,
                    bg=cell_bg,
                    fg=cell_fg,
                    padx=8,
                    pady=6,
                    anchor="center",
                    highlightthickness=1,
                    highlightbackground=BG,
                    cursor="hand2",
                )
                month_label.grid(row=row_idx, column=month_idx, sticky="nsew")
                month_label.bind(
                    "<Enter>",
                    lambda e, y=year_value, m=month_idx: self._open_bmb_detail_window(y, m, e.x_root, e.y_root),
                )
                month_label.bind("<Leave>", lambda _e: self._close_bmb_detail_window(refocus=False))

            tk.Label(
                self.bmb_table_body,
                text=self._format_number_it(annual_total, 2),
                font=("Segoe UI", 10, "bold"),
                bg=BG_TABLE,
                fg=FG_HEADER,
                padx=10,
                pady=6,
                anchor="center",
                highlightthickness=1,
                highlightbackground=BG,
            ).grid(row=row_idx, column=len(cols) - 1, sticky="nsew")

        self.bmb_table_body.update_idletasks()
        self.bmb_table_canvas.configure(scrollregion=self.bmb_table_canvas.bbox("all"))

    def _open_bmb_detail_window(self, year: int, month_idx: int, x_root: int | None = None, y_root: int | None = None):
        """Apre una finestra con i dettagli della previsione mensile per Bondora."""
        if self.bmb_detail_window is not None and self.bmb_detail_window.winfo_exists():
            self.bmb_detail_window.destroy()

        pos_x = (x_root + 18) if x_root is not None else 220
        pos_y = (y_root + 14) if y_root is not None else 220

        self.bmb_detail_window = tk.Toplevel(self)
        self.bmb_detail_window.title("Own Finance - Dettaglio previsione mensile Bondora")
        self.bmb_detail_window.geometry(f"600x400+{pos_x}+{pos_y}")
        self.bmb_detail_window.configure(bg=BG_TABLE)
        self.bmb_detail_window.minsize(500, 300)
        self.bmb_detail_window.protocol("WM_DELETE_WINDOW", lambda: self._close_bmb_detail_window(refocus=False))

        self._show_bmb_monthly_detail(self.bmb_detail_window, year, month_idx)

    def _close_bmb_detail_window(self, refocus: bool = True):
        """Chiude la finestra di dettaglio mensile."""
        if self.bmb_detail_window is not None and self.bmb_detail_window.winfo_exists():
            self.bmb_detail_window.destroy()
        self.bmb_detail_window = None
        if refocus:
            self._refocus_main()

    def _show_bmb_monthly_detail(self, parent: tk.Toplevel, year: int, month_idx: int):
        """Popola la finestra di dettaglio con le informazioni mensili."""
        wrapper = tk.Frame(parent, bg=BG_TABLE)
        wrapper.pack(fill="both", expand=True, padx=16, pady=16)

        # Header con titolo e pulsante indietro
        header_row = tk.Frame(wrapper, bg=BG_TABLE)
        header_row.pack(fill="x", pady=(0, 12))

        month_name = MESI[month_idx - 1].capitalize()
        title = f"{month_name} {year}"

        tk.Label(
             header_row,
             text=f"Previsione Bondora - {title}",
             font=("Segoe UI", 14, "bold"),
             bg=BG_TABLE,
             fg=FG_HEADER,
         ).pack(side="left", anchor="w")

        tk.Button(
             header_row,
             text="← Chiudi",
             bg=BG_FRAME,
             fg=FG,
             activebackground=SEL_BG,
             activeforeground=FG_HEADER,
             relief="flat",
             padx=10,
             command=self._close_bmb_detail_window,
         ).pack(side="right")

        # Body con i dettagli
        content = tk.Frame(wrapper, bg=BG_FRAME, padx=14, pady=14)
        content.pack(fill="both", expand=True, pady=(12, 0))

        monthly_info = self.bmb_monthly_data.get((year, month_idx), {})
        monthly_gain = float(monthly_info.get("gain", 0.0) or 0.0)
        projected_gain = float(monthly_info.get("projected_gain", 0.0) or 0.0)
        projected_gain_used = float(monthly_info.get("projected_gain_used", 0.0) or 0.0)
        projection_available = bool(monthly_info.get("projection_available", False))
        start_raw = monthly_info.get("start_balance", None)
        end_raw = monthly_info.get("end_balance", None)
        start_of_month_value = float(start_raw) if isinstance(start_raw, (int, float)) else 0.0
        end_of_month_value = float(end_raw) if isinstance(end_raw, (int, float)) else 0.0
        source = str(monthly_info.get("source", "forecast") or "forecast")

        headline_value = self._format_money_it(end_of_month_value) if projection_available else "N/D (mese storico)"

        # Infos principali
        tk.Label(
             content,
             text="Saldo atteso Bondora a fine mese",
             font=FONT_TAB,
             bg=BG_FRAME,
             fg=FG_HEADER,
         ).pack(anchor="w", pady=(0, 4))

        tk.Label(
             content,
             text=headline_value,
             font=("Segoe UI", 20, "bold"),
             bg=BG_FRAME,
             fg=FG_SOMMA,
         ).pack(anchor="w", pady=(0, 12))

        # Mostra i dettagli
        details_frame = tk.Frame(content, bg=BG_FRAME)
        details_frame.pack(fill="x", pady=(8, 0))

        # Riga: Saldo inizio mese
        row1 = tk.Frame(details_frame, bg=BG_FRAME)
        row1.pack(fill="x", pady=(0, 8))
        tk.Label(row1, text="Saldo inizio mese:", font=FONT_TABLE, bg=BG_FRAME, fg=FG_HEADER).pack(side="left")
        tk.Label(
            row1,
            text=self._format_money_it(start_of_month_value) if projection_available else "N/D",
            font=FONT_TABLE,
            bg=BG_FRAME,
            fg=FG_SOMMA,
        ).pack(side="right")

        # Riga: Guadagno stimato mese
        row2 = tk.Frame(details_frame, bg=BG_FRAME)
        row2.pack(fill="x", pady=(0, 8))
        tk.Label(row2, text="Guadagno previsionale mese:", font=FONT_TABLE, bg=BG_FRAME, fg=FG_HEADER).pack(side="left")
        tk.Label(row2, text=self._format_money_it(projected_gain_used), font=FONT_TABLE, bg=BG_FRAME, fg=FG_SOMMA).pack(side="right")

        # Riga: Saldo fine mese
        row3 = tk.Frame(details_frame, bg=BG_FRAME)
        row3.pack(fill="x", pady=(0, 8))
        tk.Label(row3, text="Saldo fine mese:", font=FONT_TABLE, bg=BG_FRAME, fg=FG_HEADER).pack(side="left")
        tk.Label(
            row3,
            text=self._format_money_it(end_of_month_value) if projection_available else "N/D",
            font=("Segoe UI", 11, "bold"),
            bg=BG_FRAME,
            fg=FG_SOMMA,
        ).pack(side="right")

        row4 = tk.Frame(details_frame, bg=BG_FRAME)
        row4.pack(fill="x", pady=(0, 8))
        tk.Label(row4, text="Valore mostrato nella cella:", font=FONT_TABLE, bg=BG_FRAME, fg=FG_HEADER).pack(side="left")
        tk.Label(row4, text=self._format_money_it(monthly_gain), font=FONT_TABLE, bg=BG_FRAME, fg=FG_SOMMA).pack(side="right")

        # Divider
        tk.Label(details_frame, text="", bg=BG_FRAME).pack(fill="x", pady=4)

        # Informazioni aggiuntive
        info_frame = tk.Frame(content, bg=BG_FRAME)
        info_frame.pack(fill="both", expand=True, pady=(12, 0))

        tk.Label(info_frame, text="Informazioni", font=FONT_TAB, bg=BG_FRAME, fg=FG_HEADER).pack(anchor="w", pady=(0, 8))

        # Nota importante
        source_text = {
            "actual": "Dati storici registrati",
            "actual+forecast": "Parte storica + parte previsionale",
            "forecast": "Valore interamente previsionale",
        }.get(source, "Valore previsionale")
        note_text = (
            "Dettaglio del mese selezionato:\n"
            f"- Origine dato: {source_text}\n"
            f"- Guadagno previsionale del mese: {self._format_money_it(projected_gain)}\n"
            "- Saldo calcolato partendo dalla cifra attuale Bondora\n"
            "  e sommando i previsionali dei mesi successivi\n"
            "- Simulazione senza nuovi versamenti\n"
            "- Gli incrementi giornalieri seguono Bondora Evolution\n\n"
            "Il saldo fine mese rappresenta la stima puntuale\n"
            "per la chiusura del mese selezionato."
        )
        tk.Label(
            info_frame,
            text=note_text,
            font=FONT_SMALL,
            bg=BG_FRAME,
            fg=FG,
            justify="left",
        ).pack(anchor="w", fill="both", expand=True)

    def _go_to_pbca_window(self):
        if self.pbca_window is not None and self.pbca_window.winfo_exists():
            self.pbca_window.deiconify()
            self.pbca_window.lift()
            self.pbca_window.focus_force()
            self._render_pbca_table()
            return

        self.pbca_window = tk.Toplevel(self)
        self.pbca_window.title("Own Finance - Previsionale Bondora con aggiunta")
        self.pbca_window.geometry("1480x560")
        self.pbca_window.configure(bg=BG_TABLE)
        self.pbca_window.minsize(1100, 420)
        self.pbca_window.protocol("WM_DELETE_WINDOW", self._close_pbca_window)

        self._build_pbca_window(self.pbca_window)
        self._render_pbca_table()

    def _close_pbca_window(self):
        if self.pbca_window is not None and self.pbca_window.winfo_exists():
            self.pbca_window.destroy()
        self.pbca_window = None
        self.pbca_table_canvas = None
        self.pbca_table_body = None
        self._refocus_main()

    def _build_pbca_window(self, parent: tk.Toplevel):
        wrapper = tk.Frame(parent, bg=BG_TABLE)
        wrapper.pack(fill="both", expand=True, padx=16, pady=16)

        header_row = tk.Frame(wrapper, bg=BG_TABLE)
        header_row.pack(fill="x")

        tk.Label(
            header_row,
            text="Previsionale Bondora con aggiunta",
            font=("Segoe UI", 12, "bold"),
            bg=BG_TABLE,
            fg=FG_HEADER,
        ).pack(side="left", anchor="w")

        tk.Button(
            header_row,
            text="← Torna indietro",
            bg=BG_FRAME,
            fg=FG,
            activebackground=SEL_BG,
            activeforeground=FG_HEADER,
            relief="flat",
            padx=10,
            command=self._close_pbca_window,
        ).pack(side="right")

        controls = tk.Frame(wrapper, bg=BG_TABLE)
        controls.pack(fill="x", pady=(14, 0))

        tk.Label(controls, text="Data aggiunta", font=FONT_SMALL, bg=BG_TABLE, fg=FG_HEADER).pack(side="left")
        date_entry = tk.Entry(
            controls,
            textvariable=self.pbca_selected_date_var,
            width=14,
            bg=BG_FRAME,
            fg=FG,
            insertbackground=FG,
            relief="flat",
            font=FONT_TABLE,
        )
        date_entry.pack(side="left", padx=(8, 2))

        tk.Button(
            controls,
            text="📅",
            font=FONT_SMALL,
            fg=FG_HEADER,
            bg=BG_FRAME,
            activeforeground=FG_HEADER,
            activebackground=SEL_BG,
            relief="flat",
            bd=0,
            padx=6,
            pady=3,
            cursor="hand2",
            command=lambda: self._open_date_picker_pbca(date_entry),
        ).pack(side="left", padx=(0, 16))

        tk.Label(controls, text="Importo aggiunto (€)", font=FONT_SMALL, bg=BG_TABLE, fg=FG_HEADER).pack(side="left")
        amount_entry = tk.Entry(
            controls,
            textvariable=self.pbca_amount_var,
            width=14,
            bg=BG_FRAME,
            fg=FG,
            insertbackground=FG,
            relief="flat",
            font=FONT_TABLE,
        )
        amount_entry.pack(side="left", padx=(8, 10))

        tk.Button(
            controls,
            text="🔄 Calcola",
            font=FONT_TAB,
            fg=FG_HEADER,
            bg=BG_FRAME,
            activeforeground=FG_HEADER,
            activebackground=SEL_BG,
            relief="flat",
            bd=0,
            padx=14,
            pady=6,
            cursor="hand2",
            command=self._render_pbca_table,
        ).pack(side="left", padx=(0, 0))

        tk.Label(
            wrapper,
            textvariable=self.pbca_hint_var,
            font=FONT_SMALL,
            bg=BG_TABLE,
            fg=FG,
            justify="left",
        ).pack(anchor="w", pady=(10, 8))

        table_wrapper = tk.Frame(wrapper, bg=BG_TABLE)
        table_wrapper.pack(fill="both", expand=True)

        self.pbca_table_canvas = tk.Canvas(table_wrapper, bg=BG_TABLE, highlightthickness=0)
        vsb = ttk.Scrollbar(table_wrapper, orient="vertical", command=self.pbca_table_canvas.yview)
        hsb = ttk.Scrollbar(table_wrapper, orient="horizontal", command=self.pbca_table_canvas.xview)
        self.pbca_table_canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        self.pbca_table_canvas.pack(side="left", fill="both", expand=True)

        self.pbca_table_body = tk.Frame(self.pbca_table_canvas, bg=BG_TABLE)
        window_id = self.pbca_table_canvas.create_window((0, 0), window=self.pbca_table_body, anchor="nw")

        def _refresh_scrollregion(_event=None):
            if self.pbca_table_canvas is not None:
                self.pbca_table_canvas.configure(scrollregion=self.pbca_table_canvas.bbox("all"))

        def _sync_width(event):
            if self.pbca_table_canvas is None or self.pbca_table_body is None:
                return
            requested = self.pbca_table_body.winfo_reqwidth()
            self.pbca_table_canvas.itemconfigure(window_id, width=max(event.width, requested))

        self.pbca_table_body.bind("<Configure>", _refresh_scrollregion)
        self.pbca_table_canvas.bind("<Configure>", _sync_width)

    def _open_date_picker_pbca(self, date_entry: tk.Entry):
        """Apre un semplice calendario per selezionare la data."""
        date_picker = tk.Toplevel(self)
        date_picker.title("Seleziona data")
        date_picker.geometry("320x250")
        date_picker.configure(bg=BG_TABLE)
        date_picker.resizable(False, False)

        try:
            current_date_str = self.pbca_selected_date_var.get().strip()
            if "/" in current_date_str:
                parts = current_date_str.split("/")
                current_date = date(int(parts[2]), int(parts[1]), int(parts[0]))
            else:
                current_date = date.today()
        except (ValueError, IndexError):
            current_date = date.today()

        year_var = tk.StringVar(value=str(current_date.year))
        month_var = tk.StringVar(value=str(current_date.month))
        day_var = tk.StringVar(value=str(current_date.day))

        frame = tk.Frame(date_picker, bg=BG_TABLE)
        frame.pack(fill="both", expand=True, padx=16, pady=16)

        tk.Label(frame, text="Anno", font=FONT_SMALL, bg=BG_TABLE, fg=FG_HEADER).pack(anchor="w")
        year_sb = ttk.Spinbox(
            frame,
            from_=2000,
            to=2100,
            textvariable=year_var,
            width=10,
        )
        year_sb.pack(anchor="w", pady=(2, 12))

        tk.Label(frame, text="Mese", font=FONT_SMALL, bg=BG_TABLE, fg=FG_HEADER).pack(anchor="w")
        month_sb = ttk.Spinbox(
            frame,
            from_=1,
            to=12,
            textvariable=month_var,
            width=10,
        )
        month_sb.pack(anchor="w", pady=(2, 12))

        tk.Label(frame, text="Giorno", font=FONT_SMALL, bg=BG_TABLE, fg=FG_HEADER).pack(anchor="w")
        day_sb = ttk.Spinbox(
            frame,
            from_=1,
            to=31,
            textvariable=day_var,
            width=10,
        )
        day_sb.pack(anchor="w", pady=(2, 12))

        def _on_ok():
            try:
                year = int(year_var.get())
                month = int(month_var.get())
                day = int(day_var.get())
                selected = date(year, month, day)
                self.pbca_selected_date_var.set(selected.strftime("%d/%m/%Y"))
                date_picker.destroy()
            except ValueError:
                messagebox.showerror("Errore", "Data non valida.")

        ok_btn = tk.Button(
            frame,
            text="OK",
            bg=BG_FRAME,
            fg=FG,
            activebackground=SEL_BG,
            activeforeground=FG_HEADER,
            relief="flat",
            padx=14,
            pady=6,
            command=_on_ok,
        )
        ok_btn.pack(anchor="e", pady=(12, 0))

    def _calculate_bondora_monthly_forecast_rows_with_addition(
        self,
        selected_date: date,
        addition_amount: float,
        horizon_years: int = 10,
    ) -> tuple[list[dict[str, object]], dict[tuple[int, int], dict[str, object]]]:
        """Calcola il previsionale mensile Bondora con un'aggiunta una tantum in una data specifica.
        
        La logica è la stessa di Previsionale mensile Bondora, ma il saldo viene aumentato di addition_amount
        nel mese della data selezionata.

        Args:
            selected_date: Data in cui è stata aggiunta la cifra
            addition_amount: Importo aggiunto
            horizon_years: Numero di anni da proiettare
        """
        today = date.today()
        start_year = today.year
        end_year = start_year + horizon_years

        current_amount, initial_daily_rate = self._get_bondora_current_snapshot()
        snapshot_amount = current_amount

        # Prepara i milestones (coppie capitale, daily_rate)
        milestones: list[tuple[float, float]] = []
        for daily, row in self.bondo_evo_data.items():
            cap_pr = row.get("cap_pr")
            try:
                cap_pr_value = float(cap_pr)
                daily_value = float(daily)
            except (TypeError, ValueError):
                continue
            if cap_pr_value <= 0.0 or daily_value <= 0.0:
                continue
            milestones.append((cap_pr_value, daily_value))
        milestones.sort(key=lambda item: item[0])

        monthly_projected: dict[tuple[int, int], float] = {
            (year, month): 0.0
            for year in range(start_year, end_year + 1)
            for month in range(1, 13)
        }

        end_date = date(end_year, 12, 31)
        
        # FASE 1: Simulazione fino al giorno PRIMA dell'aggiunta
        simulated_amount = current_amount
        daily_rate = initial_daily_rate
        milestone_idx = 0
        
        # Aggiorna daily_rate iniziale basato sui milestones
        while milestone_idx < len(milestones) and simulated_amount + 1e-9 >= milestones[milestone_idx][0]:
            daily_rate = max(daily_rate, milestones[milestone_idx][1])
            milestone_idx += 1
        
        # Simula da domani fino al giorno prima della data di aggiunta
        day_before_addition = selected_date - timedelta(days=1)
        if day_before_addition >= today:
            for day_ord in range((today + timedelta(days=1)).toordinal(), day_before_addition.toordinal() + 1):
                while milestone_idx < len(milestones) and simulated_amount + 1e-9 >= milestones[milestone_idx][0]:
                    daily_rate = max(daily_rate, milestones[milestone_idx][1])
                    milestone_idx += 1

                current_day = date.fromordinal(day_ord)
                simulated_amount += daily_rate
                key = (current_day.year, current_day.month)
                if key in monthly_projected:
                    monthly_projected[key] += daily_rate

        # FASE 2: Aggiunta importo e ricacolo del daily_rate
        simulated_amount += addition_amount
        
        # Ricacola i milestones da zero con il nuovo capitale
        daily_rate = initial_daily_rate
        milestone_idx = 0
        while milestone_idx < len(milestones) and simulated_amount + 1e-9 >= milestones[milestone_idx][0]:
            daily_rate = max(daily_rate, milestones[milestone_idx][1])
            milestone_idx += 1

        # FASE 3: Simulazione dal giorno di aggiunta fino alla fine dell'orizzonte
        if selected_date <= end_date:
            for day_ord in range(selected_date.toordinal(), end_date.toordinal() + 1):
                while milestone_idx < len(milestones) and simulated_amount + 1e-9 >= milestones[milestone_idx][0]:
                    daily_rate = max(daily_rate, milestones[milestone_idx][1])
                    milestone_idx += 1

                current_day = date.fromordinal(day_ord)
                simulated_amount += daily_rate
                key = (current_day.year, current_day.month)
                if key in monthly_projected:
                    monthly_projected[key] += daily_rate

        current_year_actual = self._get_ctm_bondora_monthly_values_for_year(str(start_year))

        # Costruisci le righe della tabella
        forecast_balance_cursor = snapshot_amount
        rows: list[dict[str, object]] = []
        month_details: dict[tuple[int, int], dict[str, object]] = {}
        
        for year in range(start_year, end_year + 1):
            monthly_values: dict[str, float] = {}
            for month_idx, month_name in enumerate(MESI, start=1):
                projected_value = float(monthly_projected.get((year, month_idx), 0.0))
                actual_value = 0.0
                source = "forecast"
                addition_in_this_month = 0.0

                if year == start_year:
                    actual_value = float(current_year_actual.get(month_name, 0.0) or 0.0)
                    if month_idx < today.month:
                        # Mesi passati: usa i dati reali
                        value = actual_value
                        source = "actual"
                    elif month_idx == today.month:
                        # Mese corrente: combina reale + proiezione
                        value = actual_value + projected_value
                        source = "actual+forecast" if actual_value > 0.0 else "forecast"
                    else:
                        # Mesi futuri: proiezione
                        value = projected_value
                        # Se l'aggiunta è in questo mese, nota il flag
                        if selected_date.year == year and selected_date.month == month_idx:
                            addition_in_this_month = addition_amount
                            source = "forecast+addition"
                else:
                    value = projected_value
                    if selected_date.year == year and selected_date.month == month_idx:
                        addition_in_this_month = addition_amount
                        source = "forecast+addition"

                # Determina se la proiezione è disponibile
                projection_available = year > start_year or (year == start_year and month_idx >= today.month)
                projected_for_balance = projected_value if projection_available else 0.0

                month_start = None
                month_end = None
                if projection_available:
                    month_start = forecast_balance_cursor
                    # Il saldo fine mese include sia il guadagno che l'aggiunta (se presente)
                    month_end = month_start + projected_for_balance + addition_in_this_month
                    forecast_balance_cursor = month_end

                # La cella mostra SOLO il guadagno mensile, non l'aggiunta
                monthly_values[month_name] = value
                month_details[(year, month_idx)] = {
                    "year": year,
                    "month_idx": month_idx,
                    "month_name": month_name,
                    "gain": value,  # Solo il guadagno effettivo del mese
                    "actual_gain": actual_value,
                    "projected_gain": projected_value,  # Solo il guadagno proiettato, non l'aggiunta
                    "projected_gain_used": projected_for_balance,
                    "addition_in_month": addition_in_this_month,  # Separato per informazione
                    "start_balance": month_start,
                    "end_balance": month_end,  # Questo include sia guadagno che aggiunta
                    "projection_available": projection_available,
                    "source": source,
                }

            annual_total = sum(monthly_values.values())
            rows.append({"year": year, "monthly": monthly_values, "annual_total": annual_total})

        return rows, month_details

    def _render_pbca_table(self):
        if self.pbca_table_body is None or self.pbca_table_canvas is None:
            return

        for child in self.pbca_table_body.winfo_children():
            child.destroy()

        # Parse date and amount
        try:
            date_str = self.pbca_selected_date_var.get().strip()
            if not date_str:
                self.pbca_hint_var.set("Errore: inserisci una data nel formato DD/MM/YYYY")
                return
            if "/" in date_str:
                parts = date_str.split("/")
                selected_date = date(int(parts[2]), int(parts[1]), int(parts[0]))
            else:
                self.pbca_hint_var.set("Errore: data non valida. Formato: DD/MM/YYYY")
                return
        except (ValueError, IndexError):
            self.pbca_hint_var.set("Errore: data non valida. Formato: DD/MM/YYYY")
            return

        try:
            amount_str = self.pbca_amount_var.get().strip()
            if not amount_str:
                self.pbca_hint_var.set("Errore: inserisci un importo positivo.")
                return
            addition_amount = float(self._parse_localized_number(amount_str) or 0.0)
            if addition_amount <= 0:
                self.pbca_hint_var.set("Errore: importo deve essere positivo.")
                return
        except (ValueError, TypeError):
            self.pbca_hint_var.set("Errore: importo non valido.")
            return

        rows, month_details = self._calculate_bondora_monthly_forecast_rows_with_addition(
            selected_date=selected_date,
            addition_amount=addition_amount,
            horizon_years=10
        )
        today = date.today()
        self.pbca_monthly_data = month_details

        if not rows:
            self.pbca_hint_var.set("Nessun dato disponibile per il previsionale.")
            tk.Label(
                self.pbca_table_body,
                text="Nessun dato disponibile.",
                bg=BG_TABLE,
                fg=FG_ACCENT,
                font=FONT_TABLE,
            ).pack(anchor="w", padx=10, pady=10)
            return

        self.pbca_hint_var.set(
            f"Previsionale con aggiunta di {self._format_money_it(addition_amount)} del {selected_date.strftime('%d/%m/%Y')}. "
            "Mesi già trascorsi dell'anno corrente evidenziati in verde. "
            "Passa con il mouse su un valore mensile per visualizzare il saldo."
        )

        cols = ["Anno"] + [month.capitalize() for month in MESI] + ["Totale"]
        for col_idx, col_name in enumerate(cols):
            width = 90 if col_name == "Anno" else (120 if col_name == "Totale" else 96)
            self.pbca_table_body.grid_columnconfigure(col_idx, minsize=width, weight=0)
            tk.Label(
                self.pbca_table_body,
                text=col_name,
                font=FONT_TAB,
                bg=BG_FRAME,
                fg=FG_HEADER,
                padx=10,
                pady=8,
                anchor="center",
                highlightthickness=1,
                highlightbackground=BG,
            ).grid(row=0, column=col_idx, sticky="nsew")

        past_month_bg = "#355d45"
        for row_idx, row in enumerate(rows, start=1):
            year_value = int(row.get("year", 0) or 0)
            monthly = row.get("monthly", {}) if isinstance(row.get("monthly", {}), dict) else {}
            annual_total = float(row.get("annual_total", 0.0) or 0.0)

            tk.Label(
                self.pbca_table_body,
                text=str(year_value),
                font=("Segoe UI", 10, "bold"),
                bg=BG_TABLE,
                fg=FG_HEADER,
                padx=10,
                pady=6,
                anchor="center",
                highlightthickness=1,
                highlightbackground=BG,
            ).grid(row=row_idx, column=0, sticky="nsew")

            for month_idx, month_name in enumerate(MESI, start=1):
                month_value = float(monthly.get(month_name, 0.0) or 0.0)
                is_past_current_year = year_value == today.year and month_idx < today.month
                cell_bg = past_month_bg if is_past_current_year else BG_TABLE
                cell_fg = FG_SOMMA if month_value > 0 else FG

                month_label = tk.Label(
                    self.pbca_table_body,
                    text=self._format_number_it(month_value, 2),
                    font=FONT_SMALL,
                    bg=cell_bg,
                    fg=cell_fg,
                    padx=8,
                    pady=6,
                    anchor="center",
                    highlightthickness=1,
                    highlightbackground=BG,
                    cursor="hand2",
                )
                month_label.grid(row=row_idx, column=month_idx, sticky="nsew")
                month_label.bind(
                    "<Enter>",
                    lambda e, y=year_value, m=month_idx: self._open_pbca_detail_window(y, m, e.x_root, e.y_root),
                )
                month_label.bind("<Leave>", lambda _e: self._close_pbca_detail_window(refocus=False))

            tk.Label(
                self.pbca_table_body,
                text=self._format_number_it(annual_total, 2),
                font=("Segoe UI", 10, "bold"),
                bg=BG_TABLE,
                fg=FG_HEADER,
                padx=10,
                pady=6,
                anchor="center",
                highlightthickness=1,
                highlightbackground=BG,
            ).grid(row=row_idx, column=len(cols) - 1, sticky="nsew")

        self.pbca_table_body.update_idletasks()
        self.pbca_table_canvas.configure(scrollregion=self.pbca_table_canvas.bbox("all"))

    def _open_pbca_detail_window(self, year: int, month_idx: int, x_root: int | None = None, y_root: int | None = None):
        """Apre una finestra con i dettagli della previsione mensile con aggiunta."""
        if self.pbca_detail_window is not None and self.pbca_detail_window.winfo_exists():
            self.pbca_detail_window.destroy()

        pos_x = (x_root + 18) if x_root is not None else 220
        pos_y = (y_root + 14) if y_root is not None else 220

        self.pbca_detail_window = tk.Toplevel(self)
        self.pbca_detail_window.title("Own Finance - Dettaglio previsione Bondora con aggiunta")
        self.pbca_detail_window.geometry(f"600x400+{pos_x}+{pos_y}")
        self.pbca_detail_window.configure(bg=BG_TABLE)
        self.pbca_detail_window.minsize(500, 300)
        self.pbca_detail_window.protocol("WM_DELETE_WINDOW", lambda: self._close_pbca_detail_window(refocus=False))

        self._show_pbca_monthly_detail(self.pbca_detail_window, year, month_idx)

    def _close_pbca_detail_window(self, refocus: bool = True):
        """Chiude la finestra di dettaglio mensile."""
        if self.pbca_detail_window is not None and self.pbca_detail_window.winfo_exists():
            self.pbca_detail_window.destroy()
        self.pbca_detail_window = None
        if refocus:
            self._refocus_main()

    def _show_pbca_monthly_detail(self, parent: tk.Toplevel, year: int, month_idx: int):
        """Popola la finestra di dettaglio con le informazioni mensili."""
        wrapper = tk.Frame(parent, bg=BG_TABLE)
        wrapper.pack(fill="both", expand=True, padx=16, pady=16)

        # Header
        header_row = tk.Frame(wrapper, bg=BG_TABLE)
        header_row.pack(fill="x", pady=(0, 12))

        month_name = MESI[month_idx - 1].capitalize()
        title = f"{month_name} {year}"

        tk.Label(
            header_row,
            text=f"Previsione Bondora - {title}",
            font=("Segoe UI", 14, "bold"),
            bg=BG_TABLE,
            fg=FG_HEADER,
        ).pack(side="left", anchor="w")

        tk.Button(
            header_row,
            text="← Chiudi",
            bg=BG_FRAME,
            fg=FG,
            activebackground=SEL_BG,
            activeforeground=FG_HEADER,
            relief="flat",
            padx=10,
            command=self._close_pbca_detail_window,
        ).pack(side="right")

        # Body
        content = tk.Frame(wrapper, bg=BG_FRAME, padx=14, pady=14)
        content.pack(fill="both", expand=True, pady=(12, 0))

        monthly_info = self.pbca_monthly_data.get((year, month_idx), {})
        monthly_gain = float(monthly_info.get("gain", 0.0) or 0.0)
        projected_gain = float(monthly_info.get("projected_gain", 0.0) or 0.0)
        projected_gain_used = float(monthly_info.get("projected_gain_used", 0.0) or 0.0)
        addition_in_month = float(monthly_info.get("addition_in_month", 0.0) or 0.0)
        projection_available = bool(monthly_info.get("projection_available", False))
        start_raw = monthly_info.get("start_balance", None)
        end_raw = monthly_info.get("end_balance", None)
        start_of_month_value = float(start_raw) if isinstance(start_raw, (int, float)) else 0.0
        end_of_month_value = float(end_raw) if isinstance(end_raw, (int, float)) else 0.0
        source = str(monthly_info.get("source", "forecast") or "forecast")

        headline_value = self._format_money_it(end_of_month_value) if projection_available else "N/D (mese storico)"

        tk.Label(
            content,
            text="Saldo atteso Bondora a fine mese",
            font=FONT_TAB,
            bg=BG_FRAME,
            fg=FG_HEADER,
        ).pack(anchor="w", pady=(0, 4))

        tk.Label(
            content,
            text=headline_value,
            font=("Segoe UI", 20, "bold"),
            bg=BG_FRAME,
            fg=FG_SOMMA,
        ).pack(anchor="w", pady=(0, 12))

        details_frame = tk.Frame(content, bg=BG_FRAME)
        details_frame.pack(fill="x", pady=(8, 0))

        row1 = tk.Frame(details_frame, bg=BG_FRAME)
        row1.pack(fill="x", pady=(0, 8))
        tk.Label(row1, text="Saldo inizio mese:", font=FONT_TABLE, bg=BG_FRAME, fg=FG_HEADER).pack(side="left")
        tk.Label(
            row1,
            text=self._format_money_it(start_of_month_value) if projection_available else "N/D",
            font=FONT_TABLE,
            bg=BG_FRAME,
            fg=FG_SOMMA,
        ).pack(side="right")

        row2 = tk.Frame(details_frame, bg=BG_FRAME)
        row2.pack(fill="x", pady=(0, 8))
        tk.Label(row2, text="Guadagno del mese:", font=FONT_TABLE, bg=BG_FRAME, fg=FG_HEADER).pack(side="left")
        tk.Label(row2, text=self._format_money_it(projected_gain_used), font=FONT_TABLE, bg=BG_FRAME, fg=FG_SOMMA).pack(side="right")

        # Se c'è un'aggiunta in questo mese, mostrala
        if addition_in_month > 0.0:
            row_addition = tk.Frame(details_frame, bg=BG_FRAME)
            row_addition.pack(fill="x", pady=(0, 8))
            tk.Label(row_addition, text="Aggiunta una tantum:", font=FONT_TABLE, bg=BG_FRAME, fg=FG_HEADER).pack(side="left")
            tk.Label(row_addition, text=self._format_money_it(addition_in_month), font=FONT_TABLE, bg=BG_FRAME, fg=FG_ACCENT).pack(side="right")

        row3 = tk.Frame(details_frame, bg=BG_FRAME)
        row3.pack(fill="x", pady=(0, 8))
        tk.Label(row3, text="Saldo fine mese:", font=FONT_TABLE, bg=BG_FRAME, fg=FG_HEADER).pack(side="left")
        tk.Label(
            row3,
            text=self._format_money_it(end_of_month_value) if projection_available else "N/D",
            font=("Segoe UI", 11, "bold"),
            bg=BG_FRAME,
            fg=FG_SOMMA,
        ).pack(side="right")

        row4 = tk.Frame(details_frame, bg=BG_FRAME)
        row4.pack(fill="x", pady=(0, 8))
        tk.Label(row4, text="Guadagno mostrato nella cella:", font=FONT_TABLE, bg=BG_FRAME, fg=FG_HEADER).pack(side="left")
        tk.Label(row4, text=self._format_money_it(monthly_gain), font=FONT_TABLE, bg=BG_FRAME, fg=FG_SOMMA).pack(side="right")

        tk.Label(details_frame, text="", bg=BG_FRAME).pack(fill="x", pady=4)

        info_frame = tk.Frame(content, bg=BG_FRAME)
        info_frame.pack(fill="both", expand=True, pady=(12, 0))

        tk.Label(info_frame, text="Informazioni", font=FONT_TAB, bg=BG_FRAME, fg=FG_HEADER).pack(anchor="w", pady=(0, 8))

        source_text = {
            "actual": "Dati storici registrati",
            "actual+forecast": "Parte storica + parte previsionale",
            "addition": "Importo aggiunto una tantum",
            "forecast": "Valore previsionale",
        }.get(source, "Valore previsionale")

        note_text = (
            "Dettaglio del mese selezionato:\n"
            f"- Origine dato: {source_text}\n"
            f"- Guadagno del mese: {self._format_money_it(projected_gain_used)}\n"
            "- Saldo calcolato partendo dalla cifra attuale Bondora\n"
            "  e sommando i previsionali dei mesi successivi\n"
            "- Gli incrementi seguono Bondora Evolution\n\n"
            "Il saldo fine mese rappresenta la stima puntuale\n"
            "per la chiusura del mese selezionato."
        )
        tk.Label(
            info_frame,
            text=note_text,
            font=FONT_SMALL,
            bg=BG_FRAME,
            fg=FG,
            justify="left",
        ).pack(anchor="w", fill="both", expand=True)

    def _go_to_mm_window(self):
        if self.mm_window is not None and self.mm_window.winfo_exists():
            self.mm_window.deiconify()
            self.mm_window.lift()
            self.mm_window.focus_force()
            return

        self.mm_window = tk.Toplevel(self)
        self.mm_window.title("Own Finance - Medie mensili")
        self.mm_window.geometry("760x220")
        self.mm_window.configure(bg=BG_TABLE)
        self.mm_window.minsize(720, 220)
        self.mm_window.protocol("WM_DELETE_WINDOW", self._close_mm_window)

        self._build_mm_window(self.mm_window)
        self._init_mm_filters()
        self._refresh_mm_selection()

    def _close_mm_window(self):
        if self.mm_window is not None and self.mm_window.winfo_exists():
            self.mm_window.destroy()
        self.mm_window = None
        self.mm_month_cb = None
        self.mm_platform_cb = None
        self.mm_year_cb = None
        self._refocus_main()

    def _build_mm_window(self, parent):
        wrapper = tk.Frame(parent, bg=BG_TABLE)
        wrapper.pack(fill="both", expand=True, padx=16, pady=16)

        header_row = tk.Frame(wrapper, bg=BG_TABLE)
        header_row.pack(fill="x")

        tk.Label(
            header_row,
            text="Medie mensili",
            font=("Segoe UI", 12, "bold"),
            bg=BG_TABLE,
            fg=FG_HEADER,
        ).pack(side="left", anchor="w")

        tk.Button(
            header_row,
            text="← Torna indietro",
            bg=BG_FRAME,
            fg=FG,
            activebackground=SEL_BG,
            activeforeground=FG_HEADER,
            relief="flat",
            padx=10,
            command=self._close_mm_window,
        ).pack(side="right")

        controls = tk.Frame(wrapper, bg=BG_TABLE)
        controls.pack(fill="x", pady=(14, 0))

        tk.Label(controls, text="Mese", font=FONT_SMALL, bg=BG_TABLE, fg=FG_HEADER).pack(side="left")
        self.mm_month_cb = ttk.Combobox(
            controls,
            textvariable=self.mm_month_var,
            state="readonly",
            width=16,
            values=[],
        )
        self.mm_month_cb.pack(side="left", padx=(8, 18))
        self.mm_month_cb.bind("<<ComboboxSelected>>", lambda _e: self._refresh_mm_selection())

        tk.Label(controls, text="Piattaforma", font=FONT_SMALL, bg=BG_TABLE, fg=FG_HEADER).pack(side="left")
        self.mm_platform_cb = ttk.Combobox(
            controls,
            textvariable=self.mm_platform_var,
            state="readonly",
            width=14,
            values=[],
        )
        self.mm_platform_cb.pack(side="left", padx=(8, 18))
        self.mm_platform_cb.bind("<<ComboboxSelected>>", lambda _e: self._refresh_mm_selection())

        tk.Label(controls, text="Anno", font=FONT_SMALL, bg=BG_TABLE, fg=FG_HEADER).pack(side="left")
        self.mm_year_cb = ttk.Combobox(
            controls,
            textvariable=self.mm_year_var,
            state="readonly",
            width=12,
            values=[],
        )
        self.mm_year_cb.pack(side="left", padx=(8, 0))
        self.mm_year_cb.bind("<<ComboboxSelected>>", lambda _e: self._refresh_mm_selection())

        # Area risultati: valore risultato + eventuale istogramma
        results_wrapper = tk.Frame(wrapper, bg=BG_TABLE)
        results_wrapper.pack(fill="both", expand=True, pady=(14, 0))

        tk.Label(
            results_wrapper,
            textvariable=self.mm_title_var,
            font=("Segoe UI", 10, "bold"),
            bg=BG_TABLE,
            fg=FG_RESIDUO,
            justify="left",
        ).pack(anchor="w")

        tk.Label(
            results_wrapper,
            textvariable=self.mm_result_var,
            font=("Segoe UI", 16, "bold"),
            bg=BG_TABLE,
            fg=FG_SOMMA,
            justify="left",
        ).pack(anchor="w", pady=(4, 0))

        self.mm_chart_frame = tk.Frame(results_wrapper, bg=BG_TABLE)
        self.mm_chart_frame.pack(fill="both", expand=True, pady=(10, 0))

    def _init_mm_filters(self):
        mesi_display = [f"{i + 1}. {m.capitalize()}" for i, m in enumerate(MESI)] + ["Totale"]
        platforms = ["Bondora", "Mintos", "Tutte"]

        years: list[str] = []
        if isinstance(self.gpp_data, dict) and self.gpp_data:
            raw_years = self.gpp_data.get("years", [])
            years = [str(y) for y in raw_years]
        if not years and isinstance(self.gt_data, dict) and self.gt_data:
            raw_years = self.gt_data.get("years", [])
            years = [str(y) for y in raw_years]

        year_options = list(years) + ["Anno Per Anno"]

        if self.mm_month_cb is not None:
            self.mm_month_cb["values"] = mesi_display
        if self.mm_platform_cb is not None:
            self.mm_platform_cb["values"] = platforms
        if self.mm_year_cb is not None:
            self.mm_year_cb["values"] = year_options

        if not self.mm_month_var.get() and mesi_display:
            current_month_idx = datetime.now().month - 1
            self.mm_month_var.set(mesi_display[current_month_idx])
        if not self.mm_platform_var.get():
            self.mm_platform_var.set("Tutte")
        if not self.mm_year_var.get() and years:
            self.mm_year_var.set(years[-1])

    def _mm_extract_month_number(self, month_display: str) -> int | None:
        """Estrae il numero del mese da una stringa come '1. Gennaio' oppure restituisce None per 'Totale'."""
        if month_display == "Totale":
            return None
        try:
            return int(month_display.split(".")[0])
        except (ValueError, IndexError):
            return None

    def _mm_extract_month_name(self, month_display: str) -> str:
        """Estrae il nome del mese dalla stringa display."""
        if month_display == "Totale":
            return "Totale"
        try:
            return month_display.split(". ")[1].lower()
        except IndexError:
            return month_display.lower()

    def _mm_calculate_average(self, platform_display: str, year: str, month_display: str) -> float:
        """
        Calcola la media mensile per una piattaforma, anno e mese specifici.
        Media = (guadagno cumulativo da gennaio a mese X) / numero del mese
        Per "Tutte": somma delle medie di tutte le piattaforme
        """
        month_num = self._mm_extract_month_number(month_display)
        month_name = self._mm_extract_month_name(month_display)

        data = self.gpp_data.get("data", {})
        if not data:
            return 0.0

        platforms_to_sum = []
        if platform_display == "Tutte":
            platforms_to_sum = self.gpp_data.get("platforms", [])
        else:
            # Mappo il nome visualizzato al nome interno
            for plat in self.gpp_data.get("platforms", []):
                if plat.capitalize() == platform_display:
                    platforms_to_sum.append(plat)
                    break

        if not platforms_to_sum:
            return 0.0

        # Calcola il cumulativo da gennaio fino al mese selezionato
        total_cumulative = 0.0
        for plat in platforms_to_sum:
            plat_data = data.get(plat, {})
            year_data = plat_data.get(year, {})
            
            if month_num is None:
                # "Totale": somma tutti i mesi
                for m in MESI:
                    total_cumulative += year_data.get(m, 0.0)
            else:
                # Somma da gennaio fino al mese selezionato
                for i in range(month_num):
                    m = MESI[i]
                    total_cumulative += year_data.get(m, 0.0)

        # Calcola la media
        if month_num is None or month_num == 0:
            # "Totale": media annuale = totale / 12
            average = total_cumulative / 12.0 if total_cumulative > 0 else 0.0
        else:
            average = total_cumulative / month_num

        return average

    def _clear_mm_chart(self):
        """Rimuove l'istogramma matplotlib se presente."""
        if self.mm_mpl_canvas is not None:
            try:
                self.mm_mpl_canvas.get_tk_widget().destroy()
            except Exception:
                pass
            self.mm_mpl_canvas = None
        if self.mm_chart_frame is not None:
            for widget in self.mm_chart_frame.winfo_children():
                widget.destroy()

    def _draw_mm_bar_chart(self, years: list, values: list, platform: str, month: str):
        """Disegna l'istogramma delle medie mensili anno per anno."""
        if self.mm_chart_frame is None:
            return
        self._clear_mm_chart()

        import numpy as np

        bg_color = BG_TABLE
        fg_color = FG
        header_color = FG_HEADER

        fig, ax = plt.subplots(figsize=(5.5, 3.8))
        fig.patch.set_facecolor(bg_color)
        ax.set_facecolor(bg_color)

        x = np.arange(len(years))
        colors = [FG_HEADER if y == str(datetime.now().year) else "#6c7086" for y in years]
        bars = ax.bar(x, values, color=colors, alpha=0.88, width=0.55)

        for bar_rect, val in zip(bars, values):
            if val > 0:
                ax.text(
                    bar_rect.get_x() + bar_rect.get_width() / 2,
                    bar_rect.get_height() + max(values) * 0.01 if max(values) > 0 else 0.01,
                    self._format_number_it(val, 2),
                    ha="center", va="bottom",
                    fontsize=7, color=fg_color,
                )

        ax.set_xticks(x)
        ax.set_xticklabels([str(y) for y in years], color=fg_color, fontsize=9)
        ax.tick_params(axis="y", colors=fg_color, labelsize=8)
        ax.spines["bottom"].set_color(fg_color)
        ax.spines["left"].set_color(fg_color)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.yaxis.label.set_color(fg_color)
        ax.set_ylabel("Media EUR", color=fg_color, fontsize=9)
        
        month_name = self._mm_extract_month_name(month)
        title = f"Media mensile – {platform} – fino a {month_name.capitalize()}"
        ax.set_title(title, color=header_color, fontsize=10, pad=8)
        ax.grid(axis="y", color="#585b70", linestyle="--", linewidth=0.5, alpha=0.6)
        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=self.mm_chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        self.mm_mpl_canvas = canvas

    def _refresh_mm_selection(self):
        """Aggiorna la visualizzazione quando cambiano i filtri."""
        if self.mm_result_var is None:
            return
        if not isinstance(self.gpp_data, dict) or not self.gpp_data:
            self.mm_title_var.set("")
            self.mm_result_var.set("Dati GPP_ANNO non disponibili")
            self._clear_mm_chart()
            return

        month = self.mm_month_var.get().strip()
        platform = self.mm_platform_var.get().strip()
        year = self.mm_year_var.get().strip()

        if not month or not platform or not year:
            self.mm_title_var.set("")
            self.mm_result_var.set("Seleziona mese, piattaforma e anno")
            self._clear_mm_chart()
            return

        years_available = self.gpp_data.get("years", [])
        years_available_str = [str(y) for y in years_available]

        if year == "Anno Per Anno":
            # Disegna istogramma con medie per ogni anno
            bar_years = []
            bar_values = []
            
            for y in sorted(years_available_str, key=int):
                avg = self._mm_calculate_average(platform, y, month)
                bar_years.append(y)
                bar_values.append(avg)

            if bar_years:
                self._draw_mm_bar_chart(bar_years, bar_values, platform, month)
                month_name = self._mm_extract_month_name(month)
                self.mm_title_var.set("")
                self.mm_result_var.set(f"Medie mensili – {platform} – fino a {month_name.capitalize()}")
            else:
                self.mm_title_var.set("")
                self.mm_result_var.set("Nessun dato disponibile per le selezioni")
                self._clear_mm_chart()
        else:
            # Anno specifico: mostra titolo (rosso) + valore (verde)
            if year not in years_available_str:
                self.mm_title_var.set("")
                self.mm_result_var.set("Anno non disponibile")
                self._clear_mm_chart()
                return

            avg = self._mm_calculate_average(platform, year, month)
            month_name = self._mm_extract_month_name(month)
            title = f"Media guadagni su {platform} a {month_name} {year}"
            self.mm_title_var.set(title)
            self.mm_result_var.set(self._format_money_it(avg))
            self._clear_mm_chart()

    def _go_to_gpp_window(self):
        if self.gpp_window is not None and self.gpp_window.winfo_exists():
            self.gpp_window.deiconify()
            self.gpp_window.lift()
            self.gpp_window.focus_force()
            return

        self.gpp_window = tk.Toplevel(self)
        self.gpp_window.title("Own Finance - Confronto Mensile")
        self.gpp_window.geometry("960x560")
        self.gpp_window.configure(bg=BG_TABLE)
        self.gpp_window.minsize=800, 480
        self.gpp_window.protocol("WM_DELETE_WINDOW", self._close_gpp_window)

        self._build_gpp_window(self.gpp_window)
        self._init_gpp_filters()
        self._refresh_gpp_selection()

    def _close_gpp_window(self):
        if self.gpp_window is not None and self.gpp_window.winfo_exists():
            self.gpp_window.destroy()
        self.gpp_window = None
        self.gpp_month_cb = None
        self.gpp_platform_cb = None
        self.gpp_compare_tree = None
        self.gpp_chart_frame = None
        self.gpp_mpl_canvas = None
        self._refocus_main()

    def _build_gpp_window(self, parent):
        wrapper = tk.Frame(parent, bg=BG_TABLE)
        wrapper.pack(fill="both", expand=True, padx=16, pady=16)

        # Header row con bottone torna indietro
        header_row = tk.Frame(wrapper, bg=BG_TABLE)
        header_row.pack(fill="x")

        tk.Label(
            header_row,
            text="Confronto mensile",
            font=("Segoe UI", 12, "bold"),
            bg=BG_TABLE,
            fg=FG_HEADER,
        ).pack(side="left", anchor="w")

        tk.Button(
            header_row,
            text="← Torna indietro",
            bg=BG_FRAME,
            fg=FG,
            activebackground=SEL_BG,
            activeforeground=FG_HEADER,
            relief="flat",
            padx=10,
            command=self._close_gpp_window,
        ).pack(side="right")

        # Filtri
        controls = tk.Frame(wrapper, bg=BG_TABLE)
        controls.pack(fill="x", pady=(12, 10))

        tk.Label(controls, text="Mese", font=FONT_SMALL, bg=BG_TABLE, fg=FG_HEADER).pack(side="left")
        self.gpp_month_cb = ttk.Combobox(
            controls,
            textvariable=self.gpp_month_var,
            state="readonly",
            width=16,
            values=[],
        )
        self.gpp_month_cb.pack(side="left", padx=(8, 20))
        self.gpp_month_cb.bind("<<ComboboxSelected>>", lambda _e: self._refresh_gpp_selection())

        tk.Label(controls, text="Piattaforma", font=FONT_SMALL, bg=BG_TABLE, fg=FG_HEADER).pack(side="left")
        self.gpp_platform_cb = ttk.Combobox(
            controls,
            textvariable=self.gpp_platform_var,
            state="readonly",
            width=20,
            values=[],
        )
        self.gpp_platform_cb.pack(side="left", padx=(8, 0))
        self.gpp_platform_cb.bind("<<ComboboxSelected>>", lambda _e: self._refresh_gpp_selection())

        # Area risultati: tabella confronto a sinistra, grafico a destra
        results_frame = tk.Frame(wrapper, bg=BG_TABLE)
        results_frame.pack(fill="both", expand=True, pady=(10, 0))

        # Tabella confronto — larghezza fissa ridotta
        table_frame = tk.Frame(results_frame, bg=BG_TABLE, width=300)
        table_frame.pack(side="left", fill="y")
        table_frame.pack_propagate(False)

        vsb = ttk.Scrollbar(table_frame, orient="vertical")
        hsb = ttk.Scrollbar(table_frame, orient="horizontal")
        self.gpp_compare_tree = ttk.Treeview(
            table_frame,
            yscrollcommand=vsb.set,
            xscrollcommand=hsb.set,
            selectmode="browse",
            height=12,
        )
        vsb.config(command=self.gpp_compare_tree.yview)
        hsb.config(command=self.gpp_compare_tree.xview)
        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        self.gpp_compare_tree.pack(fill="both", expand=True)
        self.gpp_compare_tree.tag_configure("positive", foreground="#a6e3a1")
        self.gpp_compare_tree.tag_configure("negative", foreground="#f38ba8")
        self.gpp_compare_tree.tag_configure("neutral", foreground=FG)
        self.gpp_compare_tree.tag_configure("current", foreground=FG_HEADER)

        # Frame grafico — occupa tutto lo spazio rimanente
        self.gpp_chart_frame = tk.Frame(results_frame, bg=BG_TABLE)
        self.gpp_chart_frame.pack(side="left", fill="both", expand=True, padx=(16, 0))

    def _init_gpp_filters(self):
        if not isinstance(self.gpp_data, dict) or not self.gpp_data:
            return

        # Mesi con formato numerato per la visualizzazione
        self._gpp_mesi_display = [f"{i+1}. {m.capitalize()}" for i, m in enumerate(MESI)] + ["Totale"]
        self._gpp_mesi_display_map = {f"{i+1}. {M.capitalize()}": M for i, M in enumerate(MESI)}
        self._gpp_mesi_display_map["Totale"] = "Totale"

        platforms = self.gpp_data.get("platforms", [])
        platforms_display = ["Tutte"] + [p.capitalize() for p in platforms]
        self._gpp_platform_display_map = {"Tutte": "Tutte"}
        for p in platforms:
            self._gpp_platform_display_map[p.capitalize()] = p

        if self.gpp_month_cb is not None:
            self.gpp_month_cb["values"] = self._gpp_mesi_display
        if self.gpp_platform_cb is not None:
            self.gpp_platform_cb["values"] = platforms_display

        if not self.gpp_month_var.get():
            current_month_idx = datetime.now().month - 1
            self.gpp_month_var.set(self._gpp_mesi_display[current_month_idx])
        if not self.gpp_platform_var.get():
            self.gpp_platform_var.set("Tutte")

    def _gpp_cumulative_value(self, platform_display: str, year: str, up_to_month_display: str) -> float:
        """
        Calcola la somma cumulativa da GENNAIO fino a up_to_month incluso.
        platform_display e up_to_month_display sono i valori visualizzati nel menu.
        """
        display_map = getattr(self, "_gpp_platform_display_map", {})
        platform = display_map.get(platform_display, platform_display)

        mesi_map = getattr(self, "_gpp_mesi_display_map", {})
        up_to_month = mesi_map.get(up_to_month_display, up_to_month_display)

        data = self.gpp_data.get("data", {})
        if platform == "Tutte":
            platforms = self.gpp_data.get("platforms", [])
        else:
            platforms = [platform]

        if up_to_month == "Totale":
            months_to_sum = MESI
        else:
            try:
                idx = MESI.index(up_to_month)
                months_to_sum = MESI[: idx + 1]
            except ValueError:
                months_to_sum = MESI

        total = 0.0
        for plat in platforms:
            plat_data = data.get(plat, {})
            year_data = plat_data.get(year, {})
            for m in months_to_sum:
                total += year_data.get(m, 0.0)
        return total

    def _refresh_gpp_selection(self):
        if self.gpp_compare_tree is None or self.gpp_chart_frame is None:
            return
        if not isinstance(self.gpp_data, dict) or not self.gpp_data:
            return

        month = self.gpp_month_var.get().strip()
        platform = self.gpp_platform_var.get().strip()
        if not month or not platform:
            return

        years = self.gpp_data.get("years", [])
        current_year = str(datetime.now().year)

        # Calcola valore anno corrente
        current_val = self._gpp_cumulative_value(platform, current_year, month) if current_year in years else None

        # Popola tabella confronto
        tree = self.gpp_compare_tree
        tree.delete(*tree.get_children())
        tree["columns"] = ["Anno", "Guadagno", "Delta"]
        tree["show"] = "headings"
        tree.heading("Anno", text="Anno")
        tree.heading("Guadagno", text="Guadagno")
        tree.heading("Delta", text=f"Δ vs. {current_year}")
        tree.column("Anno", width=55, anchor="center")
        tree.column("Guadagno", width=110, anchor="center")
        tree.column("Delta", width=110, anchor="center")

        bar_years = []
        bar_vals = []

        for year in sorted(years, key=int):
            val = self._gpp_cumulative_value(platform, year, month)
            bar_years.append(year)
            bar_vals.append(val)

            if year == current_year:
                delta_str = "← anno corrente"
                tag = "current"
            elif current_val is not None:
                delta = current_val - val
                delta_str = self._format_signed_number_it(delta)
                tag = "positive" if delta > 0 else ("negative" if delta < 0 else "neutral")
            else:
                delta_str = "N/D"
                tag = "neutral"

            tree.insert("", "end", values=(
                str(year),
                self._format_money_it(val, prefix="€"),
                delta_str,
            ), tags=(tag,))

        # Istogramma
        self._draw_gpp_bar_chart(bar_years, bar_vals, platform, month, current_year)

    def _clear_gpp_chart(self):
        if self.gpp_mpl_canvas is not None:
            try:
                self.gpp_mpl_canvas.get_tk_widget().destroy()
            except Exception:
                pass
            self.gpp_mpl_canvas = None
        if self.gpp_chart_frame is not None:
            for w in self.gpp_chart_frame.winfo_children():
                w.destroy()

    def _draw_gpp_bar_chart(self, years: list, values: list, platform: str, month: str, current_year: str):
        if self.gpp_chart_frame is None:
            return
        self._clear_gpp_chart()

        import numpy as np

        bg_color = BG_TABLE
        fg_color = FG
        header_color = FG_HEADER

        fig, ax = plt.subplots(figsize=(5.5, 3.8))
        fig.patch.set_facecolor(bg_color)
        ax.set_facecolor(bg_color)

        x = np.arange(len(years))
        colors = [FG_HEADER if y == current_year else "#6c7086" for y in years]
        bars = ax.bar(x, values, color=colors, alpha=0.88, width=0.55)

        for bar_rect, val in zip(bars, values):
            if val > 0:
                ax.text(
                    bar_rect.get_x() + bar_rect.get_width() / 2,
                    bar_rect.get_height() + max(values) * 0.01 if max(values) > 0 else 0.01,
                    self._format_number_it(val, 2),
                    ha="center", va="bottom",
                    fontsize=7, color=fg_color,
                )

        ax.set_xticks(x)
        ax.set_xticklabels([str(y) for y in years], color=fg_color, fontsize=9)
        ax.tick_params(axis="y", colors=fg_color, labelsize=8)
        ax.spines["bottom"].set_color(fg_color)
        ax.spines["left"].set_color(fg_color)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.yaxis.label.set_color(fg_color)
        ax.set_ylabel("EUR", color=fg_color, fontsize=9)
        mesi_map = getattr(self, "_gpp_mesi_display_map", {})
        month_key = mesi_map.get(month, month)
        label_mese = month_key if month_key == "Totale" else f"Cumulato a {month_key.capitalize()}"
        title = f"{platform} – {label_mese}"
        ax.set_title(title, color=header_color, fontsize=10, pad=8)
        ax.grid(axis="y", color="#585b70", linestyle="--", linewidth=0.5, alpha=0.6)
        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=self.gpp_chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        self.gpp_mpl_canvas = canvas

    # ── Confronto Totale Mensile ───────────────────────────────

    def _go_to_ctm_window(self):
        if self.ctm_window is not None and self.ctm_window.winfo_exists():
            self.ctm_window.deiconify()
            self.ctm_window.lift()
            self.ctm_window.focus_force()
            return

        self.ctm_window = tk.Toplevel(self)
        self.ctm_window.title("Own Finance - Confronto Totale Mensile")
        self.ctm_window.geometry("1200x520")
        self.ctm_window.configure(bg=BG_TABLE)
        self.ctm_window.minsize(900, 420)
        self.ctm_window.protocol("WM_DELETE_WINDOW", self._close_ctm_window)

        self._build_ctm_window(self.ctm_window)
        self._render_ctm_table()

    def _close_ctm_window(self):
        self._hide_ctm_tooltip()
        self._close_ctm_graph_window()
        if self.ctm_window is not None and self.ctm_window.winfo_exists():
            self.ctm_window.destroy()
        self.ctm_window = None
        self.ctm_scope_cb = None
        self.ctm_table_canvas = None
        self.ctm_table_body = None
        self._refocus_main()

    def _get_ctm_scope(self) -> str:
        scope = self.ctm_scope_var.get().strip()
        return scope if scope in MONTHLY_COMPARISON_SCOPES else MONTHLY_COMPARISON_SCOPES[0]

    def _update_ctm_hint(self):
        scope = self._get_ctm_scope()
        if scope == "Bondora + Mintos":
            self.ctm_hint_var.set(
                "Passa il mouse sulle celle mese per vedere il dettaglio Bondora/Mintos e il loro totale combinato."
            )
        else:
            self.ctm_hint_var.set(
                "Passa il mouse sulle celle mese per vedere il dettaglio Bondora/Mintos/ReLender."
            )

    def _on_ctm_scope_change(self):
        self._hide_ctm_tooltip()
        self._render_ctm_table()
        if self.ctm_graph_window is not None and self.ctm_graph_window.winfo_exists():
            self._render_ctm_graph()

    def _show_ctm_graph_window(self):
        if self.ctm_graph_window is not None and self.ctm_graph_window.winfo_exists():
            self._init_ctm_graph_filters()
            self.ctm_graph_window.deiconify()
            self.ctm_graph_window.lift()
            self.ctm_graph_window.focus_force()
            self._render_ctm_graph()
            return

        self.ctm_graph_window = tk.Toplevel(self)
        self.ctm_graph_window.title("Own Finance - Grafico confronto totale mensile")
        self.ctm_graph_window.geometry("980x560")
        self.ctm_graph_window.configure(bg=BG_TABLE)
        self.ctm_graph_window.minsize(780, 460)
        self.ctm_graph_window.protocol("WM_DELETE_WINDOW", self._close_ctm_graph_window)

        wrapper = tk.Frame(self.ctm_graph_window, bg=BG_TABLE)
        wrapper.pack(fill="both", expand=True, padx=16, pady=16)

        header_row = tk.Frame(wrapper, bg=BG_TABLE)
        header_row.pack(fill="x")

        tk.Label(
            header_row,
            textvariable=self.ctm_graph_title_var,
            font=("Segoe UI", 12, "bold"),
            bg=BG_TABLE,
            fg=FG_HEADER,
        ).pack(side="left", anchor="w")

        tk.Button(
            header_row,
            text="← Chiudi",
            bg=BG_FRAME,
            fg=FG,
            activebackground=SEL_BG,
            activeforeground=FG_HEADER,
            relief="flat",
            padx=10,
            command=self._close_ctm_graph_window,
        ).pack(side="right")

        controls = tk.Frame(wrapper, bg=BG_TABLE)
        controls.pack(fill="x", pady=(10, 0))

        tk.Label(controls, text="Anno", font=FONT_SMALL, bg=BG_TABLE, fg=FG_HEADER).pack(side="left")
        self.ctm_graph_year_cb = ttk.Combobox(
            controls,
            textvariable=self.ctm_graph_year_var,
            state="readonly",
            width=14,
            values=[],
        )
        self.ctm_graph_year_cb.pack(side="left", padx=(8, 0))
        self.ctm_graph_year_cb.bind("<<ComboboxSelected>>", lambda _e: self._render_ctm_graph())
        self._init_ctm_graph_filters()

        tk.Label(
            wrapper,
            textvariable=self.ctm_graph_hint_var,
            font=FONT_SMALL,
            bg=BG_TABLE,
            fg=FG,
            justify="left",
        ).pack(anchor="w", pady=(8, 10))

        self.ctm_graph_frame = tk.Frame(wrapper, bg=BG_TABLE)
        self.ctm_graph_frame.pack(fill="both", expand=True)
        self._render_ctm_graph()

    def _close_ctm_graph_window(self):
        if self.ctm_graph_mpl_canvas is not None:
            try:
                self.ctm_graph_mpl_canvas.get_tk_widget().destroy()
            except Exception:
                pass
            self.ctm_graph_mpl_canvas = None
        if self.ctm_graph_window is not None and self.ctm_graph_window.winfo_exists():
            self.ctm_graph_window.destroy()
        self.ctm_graph_window = None
        self.ctm_graph_frame = None
        self.ctm_graph_year_cb = None
        # Riporta in primo piano la finestra ctm padre se ancora aperta
        if self.ctm_window is not None and self.ctm_window.winfo_exists():
            self.ctm_window.lift()
            self.ctm_window.focus_force()

    def _init_ctm_graph_filters(self):
        years = [str(year) for year in self.ctm_data.get("years", [])] if isinstance(self.ctm_data, dict) else []
        options = ["Totale"] + years
        if self.ctm_graph_year_cb is not None:
            self.ctm_graph_year_cb["values"] = options
        if self.ctm_graph_year_var.get() not in options:
            self.ctm_graph_year_var.set("Totale")

    def _get_ctm_graph_year_filter(self) -> str | None:
        selected = self.ctm_graph_year_var.get().strip()
        return None if not selected or selected == "Totale" else selected

    def _clear_ctm_graph(self):
        if self.ctm_graph_mpl_canvas is not None:
            try:
                self.ctm_graph_mpl_canvas.get_tk_widget().destroy()
            except Exception:
                pass
            self.ctm_graph_mpl_canvas = None
        if self.ctm_graph_frame is not None:
            for widget in self.ctm_graph_frame.winfo_children():
                widget.destroy()

    def _render_ctm_graph(self):
        if self.ctm_graph_frame is None:
            return

        self._clear_ctm_graph()
        scope = self._get_ctm_scope()
        selected_year = self._get_ctm_graph_year_filter()
        title_suffix = "Totale" if selected_year is None else selected_year
        self.ctm_graph_title_var.set(f"Grafico confronto totale mensile – {scope} – {title_suffix}")

        points = get_monthly_comparison_chart_points(
            self.ctm_data,
            scope=scope,
            year_filter=selected_year,
            positive_only=True,
        )
        if not points:
            if selected_year is None:
                self.ctm_graph_hint_var.set("Nessun mese con guadagno positivo disponibile per la vista selezionata.")
            else:
                self.ctm_graph_hint_var.set(
                    f"Nessun mese con guadagno positivo disponibile per l'anno {selected_year}."
                )
            tk.Label(
                self.ctm_graph_frame,
                text="Nessun dato disponibile per il grafico.",
                bg=BG_TABLE,
                fg=FG_ACCENT,
                font=FONT_TABLE,
            ).pack(anchor="center", expand=True)
            return

        if selected_year is None:
            self.ctm_graph_hint_var.set(
                "Istogramma cronologico dei mesi con guadagno positivo nella vista selezionata."
            )
        else:
            self.ctm_graph_hint_var.set(
                f"Istogramma dei mesi con guadagno positivo per l'anno {selected_year}."
            )

        labels = [point["label"] for point in points]
        values = [float(point["value"]) for point in points]
        current_year = str(datetime.now().year)

        import numpy as np

        fig_width = max(7.5, min(16.0, len(labels) * 0.65))
        fig, ax = plt.subplots(figsize=(fig_width, 4.4))
        fig.patch.set_facecolor(BG_TABLE)
        ax.set_facecolor(BG_TABLE)

        x = np.arange(len(labels))
        colors = [FG_HEADER if str(point["year"]) == current_year else FG_SOMMA for point in points]
        bars = ax.bar(x, values, color=colors, alpha=0.9, width=0.62)

        max_val = max(values) if values else 0.0
        offset = max(max_val * 0.015, 0.02)
        for bar_rect, value in zip(bars, values):
            ax.text(
                bar_rect.get_x() + bar_rect.get_width() / 2,
                bar_rect.get_height() + offset,
                self._format_number_it(value, 2),
                ha="center",
                va="bottom",
                fontsize=7,
                color=FG,
                rotation=0,
            )

        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=45, ha="right", color=FG, fontsize=8)
        ax.tick_params(axis="y", colors=FG, labelsize=8)
        ax.spines["bottom"].set_color(FG)
        ax.spines["left"].set_color(FG)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.yaxis.label.set_color(FG)
        ax.set_ylabel("EUR", color=FG, fontsize=9)
        chart_title = f"{scope} – guadagni mensili"
        if selected_year is not None:
            chart_title = f"{chart_title} – {selected_year}"
        ax.set_title(chart_title, color=FG_HEADER, fontsize=10, pad=10)
        ax.grid(axis="y", color="#585b70", linestyle="--", linewidth=0.5, alpha=0.6)
        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=self.ctm_graph_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        self.ctm_graph_mpl_canvas = canvas

    def _build_ctm_window(self, parent):
        wrapper = tk.Frame(parent, bg=BG_TABLE)
        wrapper.pack(fill="both", expand=True, padx=16, pady=16)

        header_row = tk.Frame(wrapper, bg=BG_TABLE)
        header_row.pack(fill="x")

        tk.Label(
            header_row,
            text="Confronto totale mensile",
            font=("Segoe UI", 12, "bold"),
            bg=BG_TABLE,
            fg=FG_HEADER,
        ).pack(side="left", anchor="w")

        tk.Button(
            header_row,
            text="← Torna indietro",
            bg=BG_FRAME,
            fg=FG,
            activebackground=SEL_BG,
            activeforeground=FG_HEADER,
            relief="flat",
            padx=10,
            command=self._close_ctm_window,
        ).pack(side="right")

        controls = tk.Frame(wrapper, bg=BG_TABLE)
        controls.pack(fill="x", pady=(10, 8))

        tk.Label(controls, text="Vista", font=FONT_SMALL, bg=BG_TABLE, fg=FG_HEADER).pack(side="left")
        self.ctm_scope_cb = ttk.Combobox(
            controls,
            textvariable=self.ctm_scope_var,
            state="readonly",
            width=18,
            values=list(MONTHLY_COMPARISON_SCOPES),
        )
        self.ctm_scope_cb.pack(side="left", padx=(8, 12))
        self.ctm_scope_cb.bind("<<ComboboxSelected>>", lambda _e: self._on_ctm_scope_change())
        if not self.ctm_scope_var.get():
            self.ctm_scope_var.set(MONTHLY_COMPARISON_SCOPES[0])

        tk.Button(
            controls,
            text="Grafico",
            bg=BG_FRAME,
            fg=FG_HEADER,
            activebackground=SEL_BG,
            activeforeground=FG_HEADER,
            relief="flat",
            padx=12,
            command=self._show_ctm_graph_window,
        ).pack(side="left")

        tk.Label(
            wrapper,
            textvariable=self.ctm_hint_var,
            font=FONT_SMALL,
            bg=BG_TABLE,
            fg=FG,
        ).pack(anchor="w", pady=(8, 8))

        table_wrapper = tk.Frame(wrapper, bg=BG_TABLE)
        table_wrapper.pack(fill="both", expand=True)

        self.ctm_table_canvas = tk.Canvas(table_wrapper, bg=BG_TABLE, highlightthickness=0)
        vsb = ttk.Scrollbar(table_wrapper, orient="vertical", command=self.ctm_table_canvas.yview)
        hsb = ttk.Scrollbar(table_wrapper, orient="horizontal", command=self.ctm_table_canvas.xview)
        self.ctm_table_canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        self.ctm_table_canvas.pack(side="left", fill="both", expand=True)

        self.ctm_table_body = tk.Frame(self.ctm_table_canvas, bg=BG_TABLE)
        window_id = self.ctm_table_canvas.create_window((0, 0), window=self.ctm_table_body, anchor="nw")

        def _refresh_scrollregion(_event=None):
            if self.ctm_table_canvas is not None:
                self.ctm_table_canvas.configure(scrollregion=self.ctm_table_canvas.bbox("all"))

        def _sync_width(event):
            if self.ctm_table_canvas is None or self.ctm_table_body is None:
                return
            requested = self.ctm_table_body.winfo_reqwidth()
            self.ctm_table_canvas.itemconfigure(window_id, width=max(event.width, requested))

        self.ctm_table_body.bind("<Configure>", _refresh_scrollregion)
        self.ctm_table_canvas.bind("<Configure>", _sync_width)

    def _render_ctm_table(self):
        if self.ctm_table_body is None:
            return

        self._update_ctm_hint()

        for child in self.ctm_table_body.winfo_children():
            child.destroy()

        if not isinstance(self.ctm_data, dict) or not self.ctm_data:
            tk.Label(
                self.ctm_table_body,
                text="Dati confronto totale mensile non disponibili.",
                bg=BG_TABLE,
                fg=FG_ACCENT,
                font=FONT_TABLE,
            ).pack(anchor="w", padx=10, pady=10)
            return

        months = list(self.ctm_data.get("months", MESI))
        rows = list(self.ctm_data.get("rows", []))
        scope = self._get_ctm_scope()

        display_rows: list[dict[str, object]] = []
        for row in rows:
            details = row.get("details", {}) if isinstance(row.get("details", {}), dict) else {}
            monthly_totals = {
                month: get_monthly_comparison_total(
                    details.get(month, {}) if isinstance(details.get(month, {}), dict) else {},
                    scope,
                )
                for month in months
            }
            annual_total = sum(monthly_totals.values())
            if any(abs(val) > 1e-9 for val in monthly_totals.values()):
                display_rows.append(
                    {
                        "year": str(row.get("year", "")),
                        "details": details,
                        "monthly_totals": monthly_totals,
                        "annual_total": annual_total,
                    }
                )

        if not display_rows:
            tk.Label(
                self.ctm_table_body,
                text="Nessun anno con dati trovato per la vista selezionata.",
                bg=BG_TABLE,
                fg=FG_ACCENT,
                font=FONT_TABLE,
            ).pack(anchor="w", padx=10, pady=10)
            return

        headers = ["Anno"] + [m.capitalize() for m in months] + ["Totale"]
        for col_idx, header in enumerate(headers):
            width = 84 if col_idx > 0 else 80
            if header == "Totale":
                width = 96
            tk.Label(
                self.ctm_table_body,
                text=header,
                font=FONT_TAB,
                bg=BG_FRAME,
                fg=FG_HEADER,
                padx=8,
                pady=8,
                width=width // 8,
                anchor="center",
                highlightthickness=1,
                highlightbackground=BG,
            ).grid(row=0, column=col_idx, sticky="nsew")

        for row_idx, row in enumerate(display_rows, start=1):
            year = str(row.get("year", ""))
            monthly_totals = row.get("monthly_totals", {}) if isinstance(row.get("monthly_totals", {}), dict) else {}
            details = row.get("details", {}) if isinstance(row.get("details", {}), dict) else {}
            annual_total = float(row.get("annual_total", 0.0) or 0.0)

            tk.Label(
                self.ctm_table_body,
                text=year,
                font=("Segoe UI", 10, "bold"),
                bg=BG_TABLE,
                fg=FG_HEADER,
                padx=8,
                pady=7,
                anchor="center",
                highlightthickness=1,
                highlightbackground=BG,
            ).grid(row=row_idx, column=0, sticky="nsew")

            for month_col, month in enumerate(months, start=1):
                month_total = float(monthly_totals.get(month, 0.0) or 0.0)
                month_details = details.get(month, {}) if isinstance(details.get(month, {}), dict) else {}
                bondora = float(month_details.get("Bondora", 0.0) or 0.0)
                mintos = float(month_details.get("Mintos", 0.0) or 0.0)
                relender = float(month_details.get("ReLender", 0.0) or 0.0)

                cell = tk.Label(
                    self.ctm_table_body,
                    text=self._format_number_it(month_total, 2),
                    font=FONT_TABLE,
                    bg=BG_TABLE,
                    fg=FG_SOMMA if month_total >= 0 else FG_NEGATIVE,
                    padx=8,
                    pady=7,
                    anchor="center",
                    highlightthickness=1,
                    highlightbackground=BG,
                )
                cell.grid(row=row_idx, column=month_col, sticky="nsew")

                if scope == "Bondora + Mintos":
                    tooltip_text = (
                        f"{year} - {month.capitalize()}\n"
                        f"Bondora: {self._format_money_it(bondora)}\n"
                        f"Mintos: {self._format_money_it(mintos)}\n"
                        f"Totale Bondora + Mintos: {self._format_money_it(month_total)}"
                    )
                else:
                    tooltip_text = (
                        f"{year} - {month.capitalize()}\n"
                        f"Bondora: {self._format_money_it(bondora)}\n"
                        f"Mintos: {self._format_money_it(mintos)}\n"
                        f"ReLender: {self._format_money_it(relender)}\n"
                        f"Totale: {self._format_money_it(month_total)}"
                    )
                self._bind_ctm_tooltip(cell, tooltip_text)

            tk.Label(
                self.ctm_table_body,
                text=self._format_number_it(annual_total, 2),
                font=("Segoe UI", 10, "bold"),
                bg=BG_TABLE,
                fg=FG_HEADER,
                padx=8,
                pady=7,
                anchor="center",
                highlightthickness=1,
                highlightbackground=BG,
            ).grid(row=row_idx, column=len(months) + 1, sticky="nsew")

    def _bind_ctm_tooltip(self, widget: tk.Widget, text: str):
        widget.bind("<Enter>", lambda event, t=text: self._show_ctm_tooltip(event, t))
        widget.bind("<Motion>", self._move_ctm_tooltip)
        widget.bind("<Leave>", lambda _event: self._hide_ctm_tooltip())

    def _show_ctm_tooltip(self, event, text: str):
        if self.ctm_window is None or not self.ctm_window.winfo_exists():
            return
        if self.ctm_tooltip is None or not self.ctm_tooltip.winfo_exists():
            self.ctm_tooltip = tk.Toplevel(self.ctm_window)
            self.ctm_tooltip.overrideredirect(True)
            self.ctm_tooltip.attributes("-topmost", True)
            self.ctm_tooltip_label = tk.Label(
                self.ctm_tooltip,
                text="",
                bg=BG_FRAME,
                fg=FG,
                font=FONT_SMALL,
                justify="left",
                padx=8,
                pady=6,
                relief="solid",
                bd=1,
            )
            self.ctm_tooltip_label.pack()

        if self.ctm_tooltip_label is not None:
            self.ctm_tooltip_label.config(text=text)

        self._move_ctm_tooltip(event)

    def _move_ctm_tooltip(self, event):
        if self.ctm_tooltip is None or not self.ctm_tooltip.winfo_exists():
            return
        x = int(event.x_root) + 14
        y = int(event.y_root) + 12
        self.ctm_tooltip.geometry(f"+{x}+{y}")

    def _hide_ctm_tooltip(self):
        if self.ctm_tooltip is not None and self.ctm_tooltip.winfo_exists():
            self.ctm_tooltip.destroy()
        self.ctm_tooltip = None
        self.ctm_tooltip_label = None

    # ── Next to be tab ──────────────────────────────────────────

    def _build_next_to_be_tab(self, parent: tk.Frame):
        wrapper = tk.Frame(parent, bg=BG_TABLE)
        wrapper.pack(fill="both", expand=True, padx=16, pady=16)

        tk.Label(
            wrapper, text="Next to be",
            font=("Segoe UI", 12, "bold"), bg=BG_TABLE, fg=FG_HEADER,
        ).pack(anchor="w")

        controls = tk.Frame(wrapper, bg=BG_TABLE)
        controls.pack(fill="x", pady=(12, 0))

        tk.Label(controls, text="Modalità", font=FONT_SMALL, bg=BG_TABLE, fg=FG_HEADER).pack(side="left")
        mode_cb = ttk.Combobox(
            controls, textvariable=self.ntb_mode_var, state="readonly", width=16,
            values=["Previsionale", "Evolution", "Attuali vivi"],
        )
        mode_cb.pack(side="left", padx=(8, 20))
        mode_cb.bind("<<ComboboxSelected>>", lambda _e: self._refresh_ntb_display())

        tk.Label(controls, text="Importo aggiuntivo (€)", font=FONT_SMALL, bg=BG_TABLE, fg=FG_HEADER).pack(side="left")
        entry = tk.Entry(
            controls, textvariable=self.ntb_amount_var, width=14,
            bg=BG_FRAME, fg=FG, insertbackground=FG, relief="flat", font=FONT_TABLE,
        )
        entry.pack(side="left", padx=(8, 12))
        entry.bind("<Return>", lambda _e: self._refresh_ntb_display())

        tk.Button(
            controls, text="Calcola",
            bg=BG_FRAME, fg=FG_HEADER, activebackground=SEL_BG,
            activeforeground=FG_HEADER, relief="flat", padx=10,
            command=self._refresh_ntb_display,
        ).pack(side="left")

        self.ntb_content_frame = tk.Frame(wrapper, bg=BG_TABLE)
        self.ntb_content_frame.pack(fill="both", expand=True, pady=(16, 0))

    def _refresh_ntb_display(self):
        if self.ntb_content_frame is None:
            return
        for child in self.ntb_content_frame.winfo_children():
            child.destroy()
        self.ntb_evo_graph_canvas = None
        self.ntb_evo_info_frame = None
        self.ntb_evo_daily_cb = None
        self._ntb_virtual_evo_data = {}

        if not self.bondo_evo_data:
            tk.Label(
                self.ntb_content_frame,
                text="Dati non ancora caricati. Attendi il completamento del caricamento.",
                bg=BG_TABLE, fg=FG_ACCENT, font=FONT_TABLE,
            ).pack(anchor="w", pady=10)
            return

        raw_amount = self.ntb_amount_var.get().strip()
        extra = self._parse_localized_number(raw_amount) if raw_amount else 0.0
        if extra is None:
            extra = 0.0

        mode = self.ntb_mode_var.get()
        if mode == "Previsionale":
            self._build_ntb_previsionale(self.ntb_content_frame, extra)
        elif mode == "Evolution":
            self._build_ntb_evolution(self.ntb_content_frame, extra)
        else:
            self._build_ntb_attuali_vivi(self.ntb_content_frame, extra)

    # ── Next to be – Previsionale ───────────────────────────────

    def _calculate_bondora_forecast_with_extra(self, extra: float) -> tuple[float, float, float, str]:
        """Previsionale Bondora a fine anno con extra aggiunto al capitale attuale."""
        if not self.bondo_evo_data:
            return 0.0, 0.0, 0.0, "Dati Bondora Evolution non disponibili."

        today = date.today()
        end_year = date(today.year, 12, 31)

        current_amount, _ = self._get_bondora_current_snapshot()
        hypothetical = current_amount + extra

        # Daily rate ipotetico: il più alto step raggiunto con il capitale ipotetico
        sorted_vals = sorted(self.bondo_evo_data.keys())
        hyp_daily_rate = sorted_vals[0] if sorted_vals else 0.0
        for val in sorted_vals:
            cap_pr = float(self.bondo_evo_data[val].get("cap_pr", 0.0) or 0.0)
            if cap_pr <= hypothetical:
                hyp_daily_rate = val
            else:
                break

        forecast = hypothetical

        # Step futuri non ancora raggiunti con il capitale ipotetico
        events: list[tuple[date, float]] = []
        for daily, row in self.bondo_evo_data.items():
            cap_pr_step = float(row.get("cap_pr", 0.0) or 0.0)
            if cap_pr_step <= hypothetical:
                continue
            mtns_hyp = cap_pr_step - hypothetical
            if hyp_daily_rate > 0:
                days_to_reach = mtns_hyp / hyp_daily_rate
            else:
                continue
            target_dt = today + timedelta(days=days_to_reach)
            if today < target_dt <= end_year:
                events.append((target_dt, float(daily)))
        events.sort(key=lambda x: (x[0], x[1]))

        event_idx = 0
        current_rate = hyp_daily_rate
        for day_ord in range((today + timedelta(days=1)).toordinal(), end_year.toordinal() + 1):
            current_day = date.fromordinal(day_ord)
            while event_idx < len(events) and events[event_idx][0] <= current_day:
                current_rate = max(current_rate, events[event_idx][1])
                event_idx += 1
            forecast += current_rate

        projected_gain = max(0.0, forecast - hypothetical)
        hint = (
            f"Capitale attuale Bondora: {self._format_money_it(current_amount)}\n"
            f"Importo aggiuntivo ipotetico: +{self._format_money_it(extra)}\n"
            f"Capitale ipotetico totale: {self._format_money_it(hypothetical)}\n"
            f"Daily rate con capitale ipotetico: {self._format_number_it(hyp_daily_rate)} €/giorno\n"
            f"Guadagno previsionale anno: {self._format_money_it(hypothetical)} + "
            f"{self._format_money_it(projected_gain)} = {self._format_money_it(forecast)}"
        )
        return forecast, hypothetical, projected_gain, hint

    def _build_ntb_previsionale(self, parent: tk.Frame, extra: float):
        bondora_forecast, _, _, bondora_hint = self._calculate_bondora_forecast_with_extra(extra)
        mintos_forecast, _, _, mintos_hint = self._calculate_mintos_forecast()
        total_forecast = bondora_forecast + mintos_forecast
        year = datetime.now().year

        tk.Label(
            parent,
            text=f"Previsionale totale a fine {year} (con +{self._format_money_it(extra)} su Bondora)",
            font=("Segoe UI", 10, "bold"), bg=BG_TABLE, fg=FG_RESIDUO,
        ).pack(anchor="w")
        tk.Label(
            parent,
            text=self._format_money_it(total_forecast),
            font=("Segoe UI", 18, "bold"), bg=BG_TABLE, fg=FG_SOMMA,
        ).pack(anchor="w", pady=(4, 0))

        details = (
            f"Dettaglio piattaforme:\n"
            f"- Bondora: {self._format_money_it(bondora_forecast)}\n"
            f"- Mintos: {self._format_money_it(mintos_forecast)}\n"
            f"- Totale: {self._format_money_it(total_forecast)}\n\n"
            f"{bondora_hint}\n\n"
            f"Totale atteso fine anno Mintos: {self._format_money_it(mintos_forecast)}\n"
            f"{mintos_hint}"
        )
        tk.Label(
            parent,
            text=details,
            font=FONT_SMALL,
            bg=BG_TABLE,
            fg=FG,
            justify="left",
        ).pack(anchor="w", pady=(8, 0))

    # ── Next to be – Evolution ──────────────────────────────────

    def _compute_ntb_evo_data(self, extra: float) -> dict:
        """Ricalcola bondo_evo_data con extra aggiunto al capitale attuale Bondora."""
        if not self.bondo_evo_data:
            return {}

        current_amount, _ = self._get_bondora_current_snapshot()
        hypothetical = current_amount + extra
        sorted_vals = sorted(self.bondo_evo_data.keys())

        # Daily rate ipotetico
        hyp_daily_rate = sorted_vals[0] if sorted_vals else 0.01
        for val in sorted_vals:
            cap_pr = float(self.bondo_evo_data[val].get("cap_pr", 0.0) or 0.0)
            if cap_pr <= hypothetical:
                hyp_daily_rate = val
            else:
                break

        today = date.today()
        virtual_data: dict = {}
        for daily_val in sorted_vals:
            row = dict(self.bondo_evo_data[daily_val])
            cap_pr = float(row.get("cap_pr", 0.0) or 0.0)
            dtns = row.get("dtns", 0.0)

            new_mtns = cap_pr - hypothetical
            new_is_reached = new_mtns < 0

            if new_is_reached:
                new_mdtns = None
                new_target_date = None
            else:
                new_mdtns = abs(new_mtns) / hyp_daily_rate if hyp_daily_rate > 0 else row.get("mdtns")
                new_target_date = (
                    today + timedelta(days=float(new_mdtns)) if new_mdtns is not None else None
                )

            virtual_data[daily_val] = {
                "cap_pr": cap_pr,
                "dtns": dtns,
                "mtns": new_mtns,
                "mdtns": new_mdtns,
                "is_reached": new_is_reached,
                "target_date": new_target_date,
            }
        return virtual_data

    def _build_ntb_evolution(self, parent: tk.Frame, extra: float):
        self._ntb_virtual_evo_data = self._compute_ntb_evo_data(extra)
        sorted_values = sorted(self._ntb_virtual_evo_data.keys())
        sorted_display = [self._format_money_it(val, prefix="€") for val in sorted_values]

        if not sorted_display:
            tk.Label(
                parent, text="Dati Bondora Evolution non disponibili.",
                bg=BG_TABLE, fg=FG_ACCENT, font=FONT_TABLE,
            ).pack(anchor="w")
            return

        # Sub-controls: dropdown cifra giornaliera
        sub_ctrl = tk.Frame(parent, bg=BG_TABLE)
        sub_ctrl.pack(fill="x", pady=(0, 12))
        tk.Label(sub_ctrl, text="Cifra giornaliera", font=FONT_SMALL, bg=BG_TABLE, fg=FG_HEADER).pack(side="left")
        self.ntb_evo_daily_cb = ttk.Combobox(
            sub_ctrl, textvariable=self.ntb_evo_daily_var,
            state="readonly", width=25, values=sorted_display,
        )
        self.ntb_evo_daily_cb.pack(side="left", padx=(8, 0))
        self.ntb_evo_daily_cb.bind("<<ComboboxSelected>>", lambda _e: self._refresh_ntb_evo_detail())

        # Default: primo step non ancora raggiunto con il capitale ipotetico
        default_idx = 0
        for i, val in enumerate(sorted_values):
            if not self._ntb_virtual_evo_data[val]["is_reached"]:
                default_idx = i
                break
        self.ntb_evo_daily_var.set(sorted_display[default_idx])

        # Area contenuto: info a sinistra, grafico a destra
        content = tk.Frame(parent, bg=BG_TABLE)
        content.pack(fill="both", expand=True)

        self.ntb_evo_info_frame = tk.Frame(content, bg=BG_TABLE)
        self.ntb_evo_info_frame.pack(side="left", fill="both", padx=(0, 32))

        self.ntb_evo_graph_canvas = tk.Canvas(
            content, width=GRAPH_CANVAS_W, height=GRAPH_CANVAS_H,
            bg=BG_TABLE, highlightthickness=0,
        )
        self.ntb_evo_graph_canvas.pack(side="left", padx=(16, 0), pady=(0, 8))

        self._refresh_ntb_evo_detail()

    def _refresh_ntb_evo_detail(self):
        if self.ntb_evo_info_frame is None:
            return
        for child in self.ntb_evo_info_frame.winfo_children():
            child.destroy()

        selected_str = self.ntb_evo_daily_var.get().strip()
        if not selected_str:
            return
        parsed = self._parse_localized_number(selected_str)
        if parsed is None:
            return
        daily_value = float(parsed)

        data = self._ntb_virtual_evo_data.get(daily_value)
        if not data:
            return

        cap_pr      = float(data.get("cap_pr", 0.0) or 0.0)
        dtns        = float(data.get("dtns", 0.0) or 0.0)
        mtns        = float(data.get("mtns", 0.0) or 0.0)
        mdtns       = data.get("mdtns")
        target_date = data.get("target_date")
        is_reached  = bool(data.get("is_reached", False))

        # Capitale ipotetico
        current_amount, _ = self._get_bondora_current_snapshot()
        raw_amount = self.ntb_amount_var.get().strip()
        extra = self._parse_localized_number(raw_amount) if raw_amount else 0.0
        if extra is None:
            extra = 0.0
        hypothetical = current_amount + extra

        # Grafico a torta
        if self.ntb_evo_graph_canvas is not None:
            reached_for_chart = cap_pr if is_reached else hypothetical
            self._draw_pie_on_canvas(self.ntb_evo_graph_canvas, cap_pr, reached_for_chart)

        # Info labels
        tk.Label(
            self.ntb_evo_info_frame,
            text=f"Cifra obiettivo: {self._format_money_it(cap_pr)}\nGiorni effettivi obiettivo: {dtns:.0f} giorni",
            font=FONT_TABLE, bg=BG_TABLE, fg=FG, justify="left",
        ).pack(anchor="w", pady=(10, 0))

        if mtns < 0:
            mtns_color = FG_SOMMA
            mtns_text = f"Cifra mancante/esubero: {self._format_money_it(abs(mtns), prefix='EUR +')}"
        elif mtns > 0:
            mtns_color = FG_NEGATIVE
            mtns_text = f"Cifra mancante/esubero: {self._format_money_it(mtns, prefix='EUR -')}"
        else:
            mtns_color = FG
            mtns_text = "Cifra mancante/esubero: EUR 0,00"

        tk.Label(
            self.ntb_evo_info_frame,
            text=mtns_text, font=FONT_TABLE, bg=BG_TABLE, fg=mtns_color, justify="left",
        ).pack(anchor="w", pady=(5, 0))

        if is_reached:
            days_text  = "Giorni all'obiettivo: RAGGIUNTO ✓"
            days_color = FG_SOMMA
        else:
            days_text  = f"Giorni all'obiettivo: {float(mdtns):.0f} giorni" if mdtns is not None else "Giorni all'obiettivo: N/D"
            days_color = FG

        tk.Label(
            self.ntb_evo_info_frame,
            text=days_text, font=FONT_TABLE, bg=BG_TABLE, fg=days_color, justify="left",
        ).pack(anchor="w", pady=(5, 0))

        if not is_reached and target_date is not None:
            target_str = target_date.strftime("%d/%m/%Y") if hasattr(target_date, "strftime") else str(target_date)
            tk.Label(
                self.ntb_evo_info_frame,
                text=f"Giorno raggiungimento obiettivo: {target_str}",
                font=FONT_TABLE, bg=BG_TABLE, fg=FG_HEADER, justify="left",
            ).pack(anchor="w", pady=(5, 0))

    # ── Next to be – Attuali vivi ───────────────────────────────

    def _build_ntb_attuali_vivi(self, parent: tk.Frame, extra: float):
        bondora  = self._get_current_platform_amount("Bondora")
        mintos   = self._get_current_platform_amount("Mintos")
        relender = self._get_current_platform_amount(
            "ReLender", aliases=["Re Lender", "Re-Lender", "Relender"],
        )

        bondora_hyp = bondora + extra
        bm_total    = bondora_hyp + mintos
        bmr_total   = bm_total + relender

        content = tk.Frame(parent, bg=BG_TABLE)
        content.pack(fill="both", expand=True)
        content.grid_columnconfigure(0, weight=1)
        content.grid_columnconfigure(1, weight=0, minsize=300)
        content.grid_rowconfigure(0, weight=1)

        left_col  = tk.Frame(content, bg=BG_TABLE)
        left_col.grid(row=0, column=0, sticky="nsew")
        right_col = tk.Frame(content, bg=BG_TABLE)
        right_col.grid(row=0, column=1, sticky="ne", padx=(12, 0))

        # Card cumulativo 1
        card1 = tk.Frame(left_col, bg=BG_FRAME, padx=16, pady=12)
        card1.pack(anchor="w", fill="x", pady=(0, 8))
        tk.Label(card1, text="Bondora + Mintos", font=FONT_TAB, bg=BG_FRAME, fg=FG).pack(anchor="w")
        tk.Label(
            card1, text=self._format_money_it(bm_total),
            font=("Segoe UI", 16, "bold"), bg=BG_FRAME, fg=FG_SOMMA,
        ).pack(anchor="w", pady=(6, 0))

        # Card cumulativo 2
        card2 = tk.Frame(left_col, bg=BG_FRAME, padx=16, pady=12)
        card2.pack(anchor="w", fill="x")
        tk.Label(card2, text="Bondora + Mintos + ReLender", font=FONT_TAB, bg=BG_FRAME, fg=FG).pack(anchor="w")
        tk.Label(
            card2, text=self._format_money_it(bmr_total),
            font=("Segoe UI", 16, "bold"), bg=BG_FRAME, fg=FG_SOMMA,
        ).pack(anchor="w", pady=(6, 0))

        # Dettaglio piattaforme
        detail = tk.Frame(right_col, bg=BG_FRAME, padx=16, pady=12)
        detail.pack(anchor="n", fill="x")
        tk.Label(detail, text="Dettaglio piattaforme", font=FONT_TAB, bg=BG_FRAME, fg=FG_HEADER).pack(anchor="w", pady=(0, 8))

        platform_rows = [
            (f"Bondora (+{self._format_money_it(extra)})", bondora_hyp),
            ("Mintos", mintos),
            ("ReLender", relender),
        ]
        for i, (label, value) in enumerate(platform_rows):
            row_frame = tk.Frame(detail, bg=BG_FRAME)
            row_frame.pack(fill="x", pady=(0 if i == 0 else 4, 0))
            tk.Label(row_frame, text=label, font=FONT_TABLE, bg=BG_FRAME, fg=FG).pack(side="left")
            tk.Label(
                row_frame, text=self._format_money_it(value),
                font=FONT_TABLE, bg=BG_FRAME, fg=FG_SOMMA,
            ).pack(side="right")

    # ── Main-tab Line Charts ─────────────────────────────────────

    # Mapping nomi piattaforma normalizzati → etichetta display
    _MTC_PLATFORM_ALIASES: dict[str, list[str]] = {
        "Bondora":  ["bondora"],
        "Mintos":   ["mintos"],
        "ReLender": ["relender", "relender", "re lender", "re-lender"],
    }
    _MTC_LINE_COLORS = {
        "Bondora":  "#89b4fa",   # blu
        "Mintos":   "#a6e3a1",   # verde
        "ReLender": "#f9e2af",   # giallo
    }
    _MTC_TABLE_TITLES = {
        "investimenti": "Investimenti per piattaforma",
        "guadagni":     "Guadagni per piattaforma",
        "inv_guad":     "Inv + Guad per piattaforma",
    }

    def _mtc_extract_platform_value(self, df, platform_name: str, column: str) -> float:
        """Estrae il valore di una piattaforma (con alias) da una colonna del DataFrame."""
        if df is None or df.empty or "Piattaforma" not in df.columns:
            return 0.0
        aliases = set(self._MTC_PLATFORM_ALIASES.get(platform_name, [platform_name.lower()]))
        for _, row in df.iterrows():
            norm = self._normalize_platform_name(str(row.get("Piattaforma", "")))
            if norm in aliases:
                val = row.get(column, 0.0)
                return float(val) if self._is_numeric_value(val) else 0.0
        return 0.0

    def _mtc_get_inv_guad_year_value(self, df, platform_name: str) -> float:
        """Per Inv+Guad annuale usa dicembre (o ultimo mese disponibile), non TOTALE."""
        if df is None or df.empty:
            return 0.0

        if "DICEMBRE" in df.columns:
            return self._mtc_extract_platform_value(df, platform_name, "DICEMBRE")

        available_months = [m for m in MESI if m in df.columns]
        if not available_months:
            return 0.0

        return self._mtc_extract_platform_value(df, platform_name, available_months[-1])

    def _open_main_tab_chart_window(self, table_key: str):
        """Apre (o porta in primo piano) la finestra grafici per il tab specificato."""
        if self.mtc_window is not None and self.mtc_window.winfo_exists():
            if self.mtc_table_key == table_key:
                self.mtc_window.deiconify()
                self.mtc_window.lift()
                self.mtc_window.focus_force()
                return
            # Chiude la finestra precedente e ne apre una nuova per il nuovo table_key
            self._close_main_tab_chart_window()

        self.mtc_table_key = table_key
        title_label = self._MTC_TABLE_TITLES.get(table_key, table_key.capitalize())
        self.mtc_window = tk.Toplevel(self)
        self.mtc_window.title(f"Own Finance – Grafici {title_label}")
        self.mtc_window.geometry("1100x620")
        self.mtc_window.configure(bg=BG_TABLE)
        self.mtc_window.minsize(860, 500)
        self.mtc_window.protocol("WM_DELETE_WINDOW", self._close_main_tab_chart_window)

        self._build_mtc_window(self.mtc_window, title_label)
        self._init_mtc_filters()
        self._render_mtc_chart()

    def _close_main_tab_chart_window(self):
        self._clear_mtc_chart()
        if self.mtc_window is not None and self.mtc_window.winfo_exists():
            self.mtc_window.destroy()
        self.mtc_window = None
        self.mtc_chart_frame = None
        self.mtc_year_cb = None
        self.mtc_platform_cb = None
        self._refocus_main()

    def _build_mtc_window(self, win: tk.Toplevel, title_label: str):
        wrapper = tk.Frame(win, bg=BG_TABLE)
        wrapper.pack(fill="both", expand=True, padx=16, pady=16)

        header_row = tk.Frame(wrapper, bg=BG_TABLE)
        header_row.pack(fill="x")

        tk.Label(
            header_row,
            text=f"Grafici – {title_label}",
            font=("Segoe UI", 12, "bold"),
            bg=BG_TABLE,
            fg=FG_HEADER,
        ).pack(side="left", anchor="w")

        tk.Button(
            header_row,
            text="← Chiudi",
            bg=BG_FRAME,
            fg=FG,
            activebackground=SEL_BG,
            activeforeground=FG_HEADER,
            relief="flat",
            padx=10,
            command=self._close_main_tab_chart_window,
        ).pack(side="right")

        controls = tk.Frame(wrapper, bg=BG_TABLE)
        controls.pack(fill="x", pady=(12, 0))

        tk.Label(controls, text="Anno", font=FONT_SMALL, bg=BG_TABLE, fg=FG_HEADER).pack(side="left")
        self.mtc_year_cb = ttk.Combobox(
            controls,
            textvariable=self.mtc_year_var,
            state="readonly",
            width=14,
            values=[],
        )
        self.mtc_year_cb.pack(side="left", padx=(8, 20))
        self.mtc_year_cb.bind("<<ComboboxSelected>>", lambda _e: self._render_mtc_chart())

        tk.Label(controls, text="Piattaforma", font=FONT_SMALL, bg=BG_TABLE, fg=FG_HEADER).pack(side="left")
        self.mtc_platform_cb = ttk.Combobox(
            controls,
            textvariable=self.mtc_platform_var,
            state="readonly",
            width=14,
            values=["All", "Bondora", "Mintos", "ReLender"],
        )
        self.mtc_platform_cb.pack(side="left", padx=(8, 0))
        self.mtc_platform_cb.bind("<<ComboboxSelected>>", lambda _e: self._render_mtc_chart())

        self.mtc_chart_frame = tk.Frame(wrapper, bg=BG_TABLE)
        self.mtc_chart_frame.pack(fill="both", expand=True, pady=(14, 0))

    def _init_mtc_filters(self):
        years = list(self.main_tab_years)
        options = years + ["All Years"]
        if self.mtc_year_cb is not None:
            self.mtc_year_cb["values"] = options
        if self.mtc_year_var.get() not in options:
            self.mtc_year_var.set("All Years")

        if self.mtc_platform_var.get() not in ["All", "Bondora", "Mintos", "ReLender"]:
            self.mtc_platform_var.set("All")

    def _clear_mtc_chart(self):
        if self.mtc_mpl_canvas is not None:
            try:
                self.mtc_mpl_canvas.get_tk_widget().destroy()
            except Exception:
                pass
            self.mtc_mpl_canvas = None
        if self.mtc_chart_frame is not None:
            for child in self.mtc_chart_frame.winfo_children():
                try:
                    child.destroy()
                except Exception:
                    pass

    def _render_mtc_chart(self):
        if self.mtc_chart_frame is None:
            return
        self._clear_mtc_chart()

        selected_year = self.mtc_year_var.get().strip()
        selected_platform = self.mtc_platform_var.get().strip()
        table_key = self.mtc_table_key

        platforms_to_show = (
            ["Bondora", "Mintos", "ReLender"]
            if selected_platform == "All"
            else [selected_platform]
        )

        all_years = sorted(self.tables_by_year.keys(), key=int)

        if not all_years:
            tk.Label(
                self.mtc_chart_frame,
                text="Nessun dato disponibile.",
                bg=BG_TABLE,
                fg=FG_ACCENT,
                font=FONT_TABLE,
            ).pack()
            return

        if selected_year == "All Years":
            # X-axis = anni, Y = totale annuale per piattaforma
            x_labels = all_years
            series: dict[str, list[float]] = {p: [] for p in platforms_to_show}
            for year in all_years:
                df = self.tables_by_year.get(year, {}).get(table_key)
                for platform in platforms_to_show:
                    # Per Inv+Guad la colonna TOTALE non e' il valore annuale da graficare.
                    val = 0.0
                    if df is not None and not df.empty:
                        if table_key == "inv_guad":
                            val = self._mtc_get_inv_guad_year_value(df, platform)
                        elif "TOTALE" in df.columns:
                            val = self._mtc_extract_platform_value(df, platform, "TOTALE")
                        else:
                            val = sum(
                                self._mtc_extract_platform_value(df, platform, m)
                                for m in MESI if m in df.columns
                            )
                    series[platform].append(val)
            x_rotation = 0
            xlabel = "Anno"
        else:
            # X-axis = mesi dell'anno selezionato
            df = self.tables_by_year.get(selected_year, {}).get(table_key)
            month_cols = [m for m in MESI if df is not None and m in df.columns] if df is not None else []
            x_labels = [m[:3].capitalize() for m in month_cols]
            series = {p: [] for p in platforms_to_show}
            for platform in platforms_to_show:
                for month in month_cols:
                    val = self._mtc_extract_platform_value(df, platform, month) if df is not None else 0.0
                    series[platform].append(val)
            x_rotation = 30
            xlabel = f"Mesi {selected_year}"

        # Costruisci il grafico
        fig, ax = plt.subplots(figsize=(10, 4.5))
        fig.patch.set_facecolor(BG_TABLE)
        ax.set_facecolor(BG_TABLE)
        ax.tick_params(colors=FG, labelsize=8)
        ax.xaxis.label.set_color(FG)
        ax.yaxis.label.set_color(FG)
        ax.title.set_color(FG_HEADER)
        for spine in ax.spines.values():
            spine.set_edgecolor(BG_FRAME)

        x_pos = range(len(x_labels))
        has_data = False
        line_items: list[tuple[object, str, list[float]]] = []
        for platform in platforms_to_show:
            y_vals = series[platform]
            if any(abs(v) > 1e-9 for v in y_vals):
                has_data = True
            color = self._MTC_LINE_COLORS.get(platform, FG)
            line, = ax.plot(
                list(x_pos),
                y_vals,
                marker="o",
                markersize=5,
                linewidth=2,
                color=color,
                label=platform,
            )
            line_items.append((line, platform, y_vals))

        ax.set_xticks(list(x_pos))
        ax.set_xticklabels(x_labels, rotation=x_rotation, ha="right" if x_rotation else "center")
        ax.set_xlabel(xlabel, color=FG)
        table_title = self._MTC_TABLE_TITLES.get(table_key, table_key)
        year_str = selected_year if selected_year != "All Years" else "tutti gli anni"
        ax.set_title(f"{table_title} — {year_str}", color=FG_HEADER, fontsize=10)
        ax.yaxis.set_major_formatter(
            matplotlib.ticker.FuncFormatter(lambda v, _: self._format_number_it(v, 2))
        )
        if len(platforms_to_show) > 1 or has_data:
            ax.legend(
                facecolor=BG_FRAME,
                edgecolor=BG_FRAME,
                labelcolor=FG,
                fontsize=8,
            )
        ax.grid(True, color=BG_FRAME, linestyle="--", linewidth=0.5)
        fig.tight_layout(pad=1.5)

        # Tooltip hover sui pallini del grafico
        annotation = ax.annotate(
            "",
            xy=(0, 0),
            xytext=(10, 10),
            textcoords="offset points",
            bbox=dict(boxstyle="round,pad=0.3", fc=BG_FRAME, ec=FG_HEADER, alpha=0.95),
            color=FG,
            fontsize=8,
        )
        annotation.set_visible(False)

        def _on_hover(event):
            if event.inaxes != ax:
                if annotation.get_visible():
                    annotation.set_visible(False)
                    self.mtc_mpl_canvas.draw_idle()
                return

            for line, platform, y_vals in line_items:
                contains, data = line.contains(event)
                if not contains:
                    continue

                idx = data.get("ind", [None])[0]
                if idx is None or idx >= len(y_vals) or idx >= len(x_labels):
                    continue

                y_val = float(y_vals[idx])
                annotation.xy = (idx, y_val)
                annotation.set_text(
                    f"{platform}\n{x_labels[idx]}\n{self._format_money_it(y_val, prefix='€')}"
                )
                annotation.set_visible(True)
                self.mtc_mpl_canvas.draw_idle()
                return

            if annotation.get_visible():
                annotation.set_visible(False)
                self.mtc_mpl_canvas.draw_idle()

        fig.canvas.mpl_connect("motion_notify_event", _on_hover)

        self.mtc_mpl_canvas = FigureCanvasTkAgg(fig, master=self.mtc_chart_frame)
        self.mtc_mpl_canvas.draw()
        self.mtc_mpl_canvas.get_tk_widget().pack(fill="both", expand=True)
        plt.close(fig)


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()

