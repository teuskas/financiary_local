"""
app_ui.py
App desktop con 3 tab per visualizzare le tabelle del foglio 2026.
"""

import threading
import tkinter as tk
from tkinter import ttk, messagebox

from auth import get_dropbox_client
from parser_2026 import get_tables

# ── Palette colori ──────────────────────────────────────────────
BG         = "#1e1e2e"
BG_FRAME   = "#2a2a3e"
BG_TABLE   = "#2a2a3e"
FG         = "#cdd6f4"
FG_HEADER  = "#89b4fa"
FG_SOMMA   = "#a6e3a1"
FG_ACCENT  = "#f38ba8"
SEL_BG     = "#45475a"
FONT_TITLE = ("Segoe UI", 13, "bold")
FONT_TAB   = ("Segoe UI", 10, "bold")
FONT_TABLE = ("Segoe UI", 10)
FONT_SMALL = ("Segoe UI", 9)

TAB_LABELS = {
    "investimenti": "💰  Investimenti",
    "guadagni":     "📈  Guadagni",
    "inv_guad":     "📊  Inv + Guad",
}


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Financiary – 2026")
        self.geometry("1100x480")
        self.configure(bg=BG)
        self.resizable(True, True)

        self._build_header()
        self._build_notebook()
        self._build_statusbar()

        # carica i dati in background per non bloccare la UI
        threading.Thread(target=self._load_data, daemon=True).start()

    # ── Layout ──────────────────────────────────────────────────

    def _build_header(self):
        hdr = tk.Frame(self, bg=BG, pady=10)
        hdr.pack(fill="x", padx=20)
        tk.Label(hdr, text="Financiary  —  Riepilogo 2026",
                 font=FONT_TITLE, bg=BG, fg=FG_HEADER).pack(side="left")
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

        self.trees: dict[str, ttk.Treeview] = {}
        for key, label in TAB_LABELS.items():
            frame = tk.Frame(self.notebook, bg=BG_TABLE)
            self.notebook.add(frame, text=label)
            tree = self._build_treeview(frame)
            self.trees[key] = tree

    def _build_treeview(self, parent: tk.Frame) -> ttk.Treeview:
        frame = tk.Frame(parent, bg=BG_TABLE)
        frame.pack(fill="both", expand=True, padx=8, pady=8)

        vsb = ttk.Scrollbar(frame, orient="vertical")
        hsb = ttk.Scrollbar(frame, orient="horizontal")
        tree = ttk.Treeview(frame,
                            yscrollcommand=vsb.set,
                            xscrollcommand=hsb.set,
                            selectmode="browse")
        vsb.config(command=tree.yview)
        hsb.config(command=tree.xview)

        vsb.pack(side="right",  fill="y")
        hsb.pack(side="bottom", fill="x")
        tree.pack(fill="both",  expand=True)

        tree.tag_configure("somma",     foreground=FG_SOMMA,  font=("Segoe UI", 10, "bold"))
        tree.tag_configure("platform",  foreground=FG)
        tree.tag_configure("zero",      foreground="#585b70")

        return tree

    def _build_statusbar(self):
        bar = tk.Frame(self, bg=BG_FRAME, height=24)
        bar.pack(fill="x", side="bottom")
        self.lbl_status = tk.Label(bar, text="", font=FONT_SMALL,
                                   bg=BG_FRAME, fg=FG, anchor="w")
        self.lbl_status.pack(side="left", padx=10)

    # ── Data loading ────────────────────────────────────────────

    def _load_data(self):
        try:
            self._set_status("Connessione a Dropbox…")
            dbx    = get_dropbox_client()
            self._set_status("Download e parsing dati…")
            tables = get_tables(dbx)
            self.after(0, lambda: self._populate_all(tables))
            self._set_status("Dati caricati con successo.")
        except Exception as ex:
            self.after(0, lambda: messagebox.showerror("Errore", str(ex)))
            self._set_status(f"Errore: {ex}")

    def _populate_all(self, tables: dict):
        from datetime import datetime
        for key, df in tables.items():
            self._populate_tree(self.trees[key], df)
        ts = datetime.now().strftime("%d/%m/%Y %H:%M")
        self.lbl_update.config(text=f"Aggiornato: {ts}")

    def _populate_tree(self, tree: ttk.Treeview, df):
        # Pulisce eventuale contenuto precedente
        tree.delete(*tree.get_children())

        # Imposta colonne
        cols = list(df.columns)
        tree["columns"] = cols
        tree["show"]    = "headings"

        for col in cols:
            width = 110 if col != "Piattaforma" else 160
            tree.heading(col, text=col)
            tree.column(col, width=width, anchor="center" if col != "Piattaforma" else "w",
                        minwidth=60)

        # Inserisce righe
        for _, row in df.iterrows():
            values = []
            for col in cols:
                v = row[col]
                if col == "Piattaforma":
                    values.append(str(v))
                else:
                    values.append(f"€ {v:,.2f}" if isinstance(v, float) else str(v))

            tag = "somma" if str(row["Piattaforma"]).upper() == "SOMMA" else (
                  "zero"  if all(row[c] == 0.0 for c in cols if c != "Piattaforma") else "platform")
            tree.insert("", "end", values=values, tags=(tag,))

    def _set_status(self, msg: str):
        self.after(0, lambda: self.lbl_status.config(text=msg))


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()

