"""
parser_2026.py
Legge il foglio '2026' di new total inv.xlsx e restituisce
le 3 tabelle come DataFrame pronti per la UI.
"""

import io
import pandas as pd
import dropbox

MESI = ["GENNAIO", "FEBBRAIO", "MARZO", "APRILE", "MAGGIO",
        "GIUGNO", "LUGLIO", "AGOSTO", "SETTEMBRE", "OTTOBRE",
        "NOVEMBRE", "DICEMBRE"]

TITOLI = {
    "investimenti": "INVESTIMENTI PER PIATTAFORMA",
    "guadagni":     "GUADAGNI PER PIATTAFORMA",
    "inv_guad":     "INV+GUAD PER PIATTAFORMA",
}

FILE_PATH = "/me/new total inv.xlsx"
SHEET     = "2026"


def _load_raw(dbx: dropbox.Dropbox) -> pd.DataFrame:
    _, response = dbx.files_download(FILE_PATH)
    return pd.read_excel(io.BytesIO(response.content), sheet_name=SHEET, header=None)


def _extract_table(df_raw: pd.DataFrame, titolo: str) -> pd.DataFrame:
    """
    Trova la riga del titolo, usa la riga successiva come header (mesi),
    raccoglie tutte le righe di piattaforma fino a SOMMA inclusa.
    """
    title_idx = df_raw[df_raw[0] == titolo].index[0]
    header_idx = title_idx  # il titolo stesso contiene già i mesi nelle colonne 1..12

    # Colonne mesi: partono dalla col 1, finiscono dove ci sono i mesi
    # Recupero le colonne che corrispondono ai mesi (1-12) + TOTALE
    col_map = {}
    for col_i in range(1, 14):
        val = df_raw.iloc[header_idx, col_i]
        if pd.notna(val) and str(val).strip() in MESI:
            col_map[str(val).strip()] = col_i
        elif pd.notna(val) and str(val).strip() == "TOTALE":
            col_map["TOTALE"] = col_i

    # Raccoglie le righe piattaforme + SOMMA
    rows = []
    for i in range(header_idx + 1, len(df_raw)):
        cell = df_raw.iloc[i, 0]
        if pd.isna(cell):
            continue
        label = str(cell).strip()
        if label == "" :
            continue

        # Stop se incontriamo un altro titolo principale
        if label in TITOLI.values() and label != titolo:
            break

        row = {"Piattaforma": label}
        for mese, ci in col_map.items():
            val = df_raw.iloc[i, ci]
            row[mese] = round(float(val), 2) if pd.notna(val) and val != "" else 0.0
        rows.append(row)

        if label == "SOMMA":
            break

    cols = ["Piattaforma"] + [m for m in MESI if m in col_map] + (["TOTALE"] if "TOTALE" in col_map else [])
    return pd.DataFrame(rows, columns=cols)


def get_tables(dbx: dropbox.Dropbox) -> dict[str, pd.DataFrame]:
    """
    Restituisce un dizionario con le 3 tabelle:
      - 'investimenti'
      - 'guadagni'
      - 'inv_guad'
    """
    df_raw = _load_raw(dbx)
    return {
        "investimenti": _extract_table(df_raw, TITOLI["investimenti"]),
        "guadagni":     _extract_table(df_raw, TITOLI["guadagni"]),
        "inv_guad":     _extract_table(df_raw, TITOLI["inv_guad"]),
    }

