"""
app_ui.py
App desktop con 3 tab per visualizzare le tabelle del foglio 2026.
"""

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
                         detect_current_year_sheet, invalidate_cache, MESI)
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
    "investimenti_attuali_vivi": "💵  Investimenti attuali vivi",
}


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
        self.geometry("1100x480")
        self.configure(bg=BG)
        self.resizable(True, True)

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
        self.bondo_evo_info_frame: tk.Frame | None = None
        self.bondo_evo_info_frame: tk.Frame | None = None

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
        self.pv_platform_cb: ttk.Combobox | None = None
        self.pv_title_var = tk.StringVar(value="")
        self.pv_result_var = tk.StringVar(value="Seleziona una piattaforma per calcolare il previsionale.")
        self.pv_hint_var = tk.StringVar(value="")

        self.live_bm_value_var = tk.StringVar(value="EUR --")
        self.live_bmr_value_var = tk.StringVar(value="EUR --")
        self.live_bondora_value_var = tk.StringVar(value="EUR --")
        self.live_mintos_value_var = tk.StringVar(value="EUR --")
        self.live_relender_value_var = tk.StringVar(value="EUR --")

        self._build_header()
        self._build_notebook()
        self._build_statusbar()

        # carica i dati in background per non bloccare la UI
        threading.Thread(target=self._load_data, daemon=True).start()

    # ── Layout ──────────────────────────────────────────────────

    def _build_header(self):
        hdr = tk.Frame(self, bg=BG, pady=10)
        hdr.pack(fill="x", padx=20)
        self.lbl_header = tk.Label(hdr, text=f"Own Finance  —  Riepilogo {self.current_year_sheet}",
                 font=FONT_TITLE, bg=BG, fg=FG_HEADER)
        self.lbl_header.pack(side="left")
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
            else:
                self.table_views[key] = self._build_data_table(frame)

    def _build_data_table(self, parent: tk.Frame) -> dict[str, tk.Widget]:
        frame = tk.Frame(parent, bg=BG_TABLE)
        frame.pack(fill="both", expand=True, padx=8, pady=8)

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

    def _populate_data_table(self, table_view: dict[str, tk.Widget], df):
        body = table_view["body"]
        canvas = table_view["canvas"]

        for child in body.winfo_children():
            child.destroy()

        cols = list(df.columns)
        numeric_cols = [col for col in cols if col != "Piattaforma"]

        for col_idx, col in enumerate(cols):
            body.grid_columnconfigure(col_idx, minsize=160 if col == "Piattaforma" else 110, weight=0)
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

        # Canvas per il grafico a torta
        self.bondo_evo_graph_canvas = tk.Canvas(
            content,
            width=GRAPH_CANVAS_W,
            height=GRAPH_CANVAS_H,
            bg=BG_TABLE,
            highlightthickness=0,
        )
        self.bondo_evo_graph_canvas.pack(side="left", padx=(16, 0), pady=(0, 8))

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
            self.after(0, lambda: self._populate_all(tables, goals, gt_anno, bondo_evo_data, gpp_data, sheet_anno))
            self._set_status("Dati caricati con successo.")
        except Exception as ex:
            self.after(0, lambda: messagebox.showerror("Errore", str(ex)))
            self._set_status(f"Errore: {ex}")

    def _populate_all(self, tables: dict, goals: dict[str, float], gt_anno: dict[str, object],
                      bondo_evo_data: dict[float, dict[str, object]], gpp_data: dict[str, object],
                      sheet_anno: str):
        self.tables = tables
        self.platform_goals = goals
        self.gt_data = gt_anno
        self.bondo_evo_data = bondo_evo_data
        self.gpp_data = gpp_data
        self.current_year_sheet = sheet_anno

        # Aggiorna titolo finestra e header con l'anno rilevato
        self.title(f"Own Finance – {sheet_anno}")
        self.lbl_header.config(text=f"Own Finance  —  Riepilogo {sheet_anno}")

        for key, df in tables.items():
            self._populate_data_table(self.table_views[key], df)
        self._init_graph_filters()
        self._refresh_graph()
        self._init_gt_anno_filters()
        self._refresh_gt_anno_selection()
        self._init_bondo_evo_filters()
        self._refresh_bondo_evo_display()
        self._refresh_live_investments_tab()
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

    def _back_to_progressive_tab(self):
        """Ritorna al tab Statistiche progressive e chiude la finestra GT_ANNO."""
        if self.gt_window is not None and self.gt_window.winfo_exists():
            self._close_gt_anno_window()

        frame = self.tab_frames.get("statistiche_progressive")
        if frame is not None:
            self.notebook.select(frame)

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
            return

        sorted_values = list(self.bondo_evo_data.keys())
        sorted_display = [self._format_money_it(val, prefix="€") for val in sorted_values]

        if self.bondo_evo_daily_cb is not None:
            self.bondo_evo_daily_cb["values"] = sorted_display

        if sorted_display and not self.bondo_evo_daily_var.get():
            self.bondo_evo_daily_var.set(sorted_display[0])

    def _draw_bondo_evo_pie_chart(self, cap_pr: float, reached: float):
        """Disegna il grafico a torta per Bondora Evolution.

        Args:
            cap_pr: Cifra obiettivo (100%)
            reached: Cifra attualmente raggiunta
        """
        if self.bondo_evo_graph_canvas is None:
            return

        c = self.bondo_evo_graph_canvas
        c.delete("all")

        cw = GRAPH_CANVAS_W
        ch = GRAPH_CANVAS_H
        cx, cy = cw // 2, ch // 2
        diameter = min(PIE_MIN_DIAMETER, cw - PIE_MARGIN * 2)
        radius = diameter // 2

        x0 = cx - radius
        y0 = cy - radius
        x1 = cx + radius
        y1 = cy + radius

        if cap_pr > 0:
            completed_ratio = reached / cap_pr
        else:
            completed_ratio = 0

        completed_ratio = max(0, min(completed_ratio, 1))
        extent = min(359.9, completed_ratio * 360)

        c.create_oval(x0, y0, x1, y1, fill=FG_RESIDUO, outline="")
        if extent > 0:
            c.create_arc(x0, y0, x1, y1, start=90, extent=-extent, fill=FG_SOMMA, outline="")

        c.create_text((x0 + x1) / 2, (y0 + y1) / 2, text=f"{completed_ratio * 100:.1f}%", fill=FG_PERCENT, font=("Segoe UI", 18, "bold"))

        legend_y = min(ch - 14, y1 + 16)
        c.create_rectangle(40, legend_y - 7, 54, legend_y + 7, fill=FG_SOMMA, outline="")
        c.create_text(110, legend_y, text="Completato", fill=FG, font=FONT_SMALL)
        c.create_rectangle(cw - 130, legend_y - 7, cw - 116, legend_y + 7, fill=FG_RESIDUO, outline="")
        c.create_text(cw - 60, legend_y, text="Residuo", fill=FG, font=FONT_SMALL)

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

        tk.Label(
            content,
            textvariable=self.pv_hint_var,
            font=FONT_SMALL,
            bg=BG_TABLE,
            fg=FG,
            justify="left",
        ).pack(anchor="w", pady=(8, 0))

    def _init_pv_filters(self):
        values = ["Bondora", "Mintos", "Tutte"]
        if self.pv_platform_cb is not None:
            self.pv_platform_cb["values"] = values
        if not self.pv_platform_var.get():
            self.pv_platform_var.set("Tutte")

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
            f"Daily iniziale: {self._format_money_it(daily_rate, prefix='EUR/giorno')}\n"
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
            self.pv_title_var.set("")
            self.pv_result_var.set("Seleziona una piattaforma")
            self.pv_hint_var.set("")
            return

        bondora_forecast, bondora_current, bondora_projected, bondora_hint = self._calculate_bondora_forecast()
        mintos_forecast, mintos_current, mintos_projected, mintos_hint = self._calculate_mintos_forecast()
        year = datetime.now().year

        if platform == "Bondora":
            self.pv_title_var.set(f"Previsionale Bondora a fine {year}")
            self.pv_result_var.set(self._format_money_it(bondora_forecast))
            self.pv_hint_var.set(bondora_hint)
        elif platform == "Mintos":
            self.pv_title_var.set(f"Previsionale Mintos a fine {year}")
            self.pv_result_var.set(self._format_money_it(mintos_forecast))
            self.pv_hint_var.set(
                f"Totale atteso fine anno Mintos: {self._format_money_it(mintos_forecast)}\n"
                f"{mintos_hint}"
            )
        else:
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


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()

