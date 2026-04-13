"""
parser_2026.py
Legge il foglio dell'anno corrente (es. '2026', '2027'...) di new total inv.xlsx
e restituisce le tabelle come DataFrame pronti per la UI.
"""

import io
import math
from datetime import datetime, timedelta
import pandas as pd
import dropbox

MESI = ["GENNAIO", "FEBBRAIO", "MARZO", "APRILE", "MAGGIO",
        "GIUGNO", "LUGLIO", "AGOSTO", "SETTEMBRE", "OTTOBRE",
        "NOVEMBRE", "DICEMBRE"]

# Mappa mesi abbreviati (GPP_ANNO) -> mesi completi
MESI_ABBR = ["GEN", "FEB", "MAR", "APR", "MAG", "GIU",
             "LUG", "AGO", "SET", "OTT", "NOV", "DIC"]
MESI_ABBR_TO_FULL = dict(zip(MESI_ABBR, MESI))

TITOLI = {
    "investimenti": "INVESTIMENTI PER PIATTAFORMA",
    "guadagni":     "GUADAGNI PER PIATTAFORMA",
    "inv_guad":     "INV+GUAD PER PIATTAFORMA",
}

FILE_PATH = "/me/new total inv.xlsx"
ARCHIVE_FOLDER_PATH = "/me/ARCHIVIO INV"
ARCHIVE_FILE_CANDIDATES = [
    "/me/ARCHIVIO INV/ARCHIVIO INV.xlsx",
    "/me/ARCHIVIO INV/ARCHIVIO INV.xlsm",
    "/ARCHIVIO INV/ARCHIVIO INV.xlsx",
    "/ARCHIVIO INV/ARCHIVIO INV.xlsm",
]
SHEET_GT_ANNO = "GT_ANNO"
SHEET_BONDO_EVO = "Bondo_Evo"
SHEET_GPP_ANNO = "GPP_ANNO"

MONTHLY_COMPARISON_SCOPES = ("Totale", "Bondora + Mintos")

GT_TITLE_GUADAGNI = "PIATTAFORMA/ANNO"
GT_TITLE_MEDIE = "MEDIA 12 M"

# Celle fisse richieste: piattaforme in E37/E38, obiettivi in G37/G38.
_FIXED_PLATFORM_ROWS = [36, 37]  # indici zero-based
_PLATFORM_COL = 4
_GOAL_COL = 6

# Fin - Inv: debiti da celle fisse del foglio annuale
_FIN_HOME_ROW = 43  # D44 -> index 43 (zero-based)
_FIN_CAR_ROW = 45   # D46 -> index 45 (zero-based)
_FIN_VALUE_COL = 3  # colonna D -> index 3

# Cache del contenuto grezzo dei file per evitare download multipli
_file_cache: dict[str, bytes] = {}


def _download_file(dbx: dropbox.Dropbox, file_path: str = FILE_PATH) -> bytes:
    """Scarica il file richiesto una sola volta per sessione e lo mette in cache."""
    global _file_cache
    if file_path not in _file_cache:
        _, response = dbx.files_download(file_path)
        _file_cache[file_path] = response.content
    return _file_cache[file_path]


def invalidate_cache():
    """Invalida la cache del file (utile se si vuole ricaricare i dati)."""
    global _file_cache
    _file_cache = {}


def detect_current_year_sheet(dbx: dropbox.Dropbox) -> str:
    """
    Legge i fogli presenti nel file Excel e restituisce il nome del foglio
    corrispondente all'anno più recente (es. '2026', '2027'...).
    Se non trova fogli con formato anno, torna all'anno corrente come stringa.
    """
    content = _download_file(dbx)
    xl = pd.ExcelFile(io.BytesIO(content))
    sheet_names = xl.sheet_names

    year_sheets = []
    for name in sheet_names:
        s = str(name).strip()
        try:
            y = int(s)
            if 2000 <= y <= 2100:
                year_sheets.append(y)
        except ValueError:
            pass

    if year_sheets:
        return str(max(year_sheets))
    return str(datetime.now().year)


def _load_raw(dbx: dropbox.Dropbox, sheet_name: str) -> pd.DataFrame:
    content = _download_file(dbx)
    return pd.read_excel(io.BytesIO(content), sheet_name=sheet_name, header=None)


def _load_raw_from_content(content: bytes, sheet_name: str) -> pd.DataFrame:
    return pd.read_excel(io.BytesIO(content), sheet_name=sheet_name, header=None)


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
            row[mese] = _safe_float(val)
        rows.append(row)

        if label == "SOMMA":
            break

    cols = ["Piattaforma"] + [m for m in MESI if m in col_map] + (["TOTALE"] if "TOTALE" in col_map else [])
    return pd.DataFrame(rows, columns=cols)


def _safe_float(value) -> float:
    if pd.isna(value) or value == "":
        return 0.0
    return round(float(value), 2)


def _looks_like_year(value) -> bool:
    if pd.isna(value):
        return False

    if isinstance(value, (int, float)):
        y = int(float(value))
        return 2000 <= y <= 2100

    text = str(value).strip()
    if text == "":
        return False

    try:
        y = int(float(text.replace(",", ".")))
    except ValueError:
        return False

    return 2000 <= y <= 2100


def _extract_gt_table(df_raw: pd.DataFrame, title_idx: int, stop_idx: int | None = None) -> pd.DataFrame:
    # Nel foglio GT_ANNO l'header (anni) e' sulla stessa riga del titolo tabella.
    col_map: dict[str, int] = {}
    upper_col_limit = min(df_raw.shape[1], 40)
    for col_i in range(1, upper_col_limit):
        val = df_raw.iloc[title_idx, col_i]
        if _looks_like_year(val):
            col_map[str(int(float(val)))] = col_i
        elif pd.notna(val) and str(val).strip().upper() == "TOTALE":
            col_map["TOTALE"] = col_i

    rows = []
    end = stop_idx if stop_idx is not None else len(df_raw)
    for i in range(title_idx + 1, end):
        cell = df_raw.iloc[i, 0]
        if pd.isna(cell):
            continue

        label = str(cell).strip()
        if label == "":
            continue

        row = {"Piattaforma": label}
        for year_col, ci in col_map.items():
            row[year_col] = _safe_float(df_raw.iloc[i, ci])
        rows.append(row)

        if label.upper() in {"SOMMA", "TOTALE"}:
            break

    ordered_years = sorted([c for c in col_map.keys() if c.isdigit()], key=int)
    cols = ["Piattaforma"] + ordered_years + (["TOTALE"] if "TOTALE" in col_map else [])
    return pd.DataFrame(rows, columns=cols)


def _normalize_text(value) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip().upper()
    # Normalizza varianti tipo "PIATTAFORMA / ANNO" -> "PIATTAFORMA/ANNO"
    text = text.replace(" / ", "/").replace("/ ", "/").replace(" /", "/")
    return " ".join(text.split())


def _normalize_platform_key(value: str) -> str:
    return (
        str(value)
        .strip()
        .lower()
        .replace(" ", "")
        .replace("_", "")
        .replace("-", "")
    )


def _extract_year_sheets_from_content(content: bytes) -> list[str]:
    xl = pd.ExcelFile(io.BytesIO(content))
    years: list[str] = []
    for name in xl.sheet_names:
        raw = str(name).strip()
        try:
            year = int(raw)
        except ValueError:
            continue
        if 2000 <= year <= 2100:
            years.append(str(year))
    return sorted(years, key=int)


def _find_archive_file_path(dbx: dropbox.Dropbox) -> str | None:
    for path in ARCHIVE_FILE_CANDIDATES:
        try:
            dbx.files_get_metadata(path)
            return path
        except Exception:
            continue

    # Fallback: cerca un file excel nella cartella ARCHIVIO INV
    try:
        result = dbx.files_list_folder(ARCHIVE_FOLDER_PATH)
    except Exception:
        return None

    for entry in result.entries:
        name = getattr(entry, "name", "")
        lower_name = str(name).lower()
        if lower_name.startswith("archivio inv") and lower_name.endswith((".xlsx", ".xlsm")):
            return getattr(entry, "path_display", None) or getattr(entry, "path_lower", None)
    return None


def _extract_monthly_platform_breakdown(df_raw: pd.DataFrame) -> dict[str, dict[str, float]]:
    guadagni_df = _extract_table(df_raw, TITOLI["guadagni"])
    if guadagni_df is None or guadagni_df.empty:
        return {}

    target_aliases = {
        "Bondora": ["Bondora"],
        "Mintos": ["Mintos"],
        "ReLender": ["ReLender", "Re Lender", "Re-Lender", "Relender"],
    }
    normalized_targets = {
        platform: {_normalize_platform_key(alias) for alias in aliases}
        for platform, aliases in target_aliases.items()
    }

    rows_by_platform: dict[str, pd.Series] = {}
    for _, row in guadagni_df.iterrows():
        label = str(row.get("Piattaforma", "")).strip()
        norm = _normalize_platform_key(label)
        for platform, aliases in normalized_targets.items():
            if norm in aliases:
                rows_by_platform[platform] = row

    monthly: dict[str, dict[str, float]] = {}
    for month in MESI:
        if month not in guadagni_df.columns:
            continue
        details = {
            platform: float(_safe_float(rows_by_platform.get(platform, {}).get(month, 0.0)))
            if platform in rows_by_platform else 0.0
            for platform in ("Bondora", "Mintos", "ReLender")
        }
        details["Totale"] = details["Bondora"] + details["Mintos"] + details["ReLender"]
        monthly[month] = details

    return monthly


def get_monthly_comparison_total(month_details: dict[str, float] | None, scope: str = "Totale") -> float:
    """Restituisce il totale mensile coerente con la vista selezionata."""
    details = month_details if isinstance(month_details, dict) else {}
    bondora = float(details.get("Bondora", 0.0) or 0.0)
    mintos = float(details.get("Mintos", 0.0) or 0.0)
    relender = float(details.get("ReLender", 0.0) or 0.0)

    if scope == "Bondora + Mintos":
        return bondora + mintos
    return bondora + mintos + relender


def get_monthly_comparison_chart_points(
    comparison_data: dict[str, object] | None,
    scope: str = "Totale",
    year_filter: str | None = None,
    positive_only: bool = True,
) -> list[dict[str, object]]:
    """Appiattisce il confronto mensile in una serie cronologica pronta per il grafico."""
    data = comparison_data if isinstance(comparison_data, dict) else {}
    months = list(data.get("months", MESI))
    rows = list(data.get("rows", []))
    points: list[dict[str, object]] = []

    for row in rows:
        year = str(row.get("year", "")).strip()
        details = row.get("details", {}) if isinstance(row.get("details", {}), dict) else {}
        if not year:
            continue
        if year_filter and year_filter != "Totale" and year != str(year_filter):
            continue

        for month in months:
            month_details = details.get(month, {}) if isinstance(details.get(month, {}), dict) else {}
            value = get_monthly_comparison_total(month_details, scope)
            if positive_only and value <= 0:
                continue
            if not positive_only and abs(value) <= 1e-9:
                continue

            month_idx = MESI.index(month) if month in MESI else len(MESI)
            label = f"{month[:3].capitalize()} {year}"
            points.append(
                {
                    "year": year,
                    "month": month,
                    "month_index": month_idx,
                    "label": label,
                    "value": float(value),
                }
            )

    points.sort(key=lambda item: (int(item["year"]), int(item["month_index"])))
    return points


def _build_yearly_monthly_data_from_content(content: bytes, year_sheets: list[str]) -> dict[str, dict[str, dict[str, float]]]:
    output: dict[str, dict[str, dict[str, float]]] = {}
    for year in year_sheets:
        try:
            df_raw = _load_raw_from_content(content, year)
            monthly = _extract_monthly_platform_breakdown(df_raw)
            if monthly:
                output[year] = monthly
        except Exception:
            continue
    return output


def get_total_monthly_comparison_data(dbx: dropbox.Dropbox) -> dict[str, object]:
    """
    Restituisce il confronto totale mensile (Bondora + Mintos + ReLender) su base annuale.

    Sorgenti:
    - anni storici: file ARCHIVIO INV in /me/ARCHIVIO INV
    - anno corrente: file NEW TOTAL INV (sheet anno corrente rilevato automaticamente)
    """
    current_content = _download_file(dbx, FILE_PATH)
    current_year = detect_current_year_sheet(dbx)

    # Storico da ARCHIVIO INV
    merged_year_data: dict[str, dict[str, dict[str, float]]] = {}
    archive_path = _find_archive_file_path(dbx)
    if archive_path:
        try:
            archive_content = _download_file(dbx, archive_path)
            archive_years = _extract_year_sheets_from_content(archive_content)
            merged_year_data.update(_build_yearly_monthly_data_from_content(archive_content, archive_years))
        except Exception:
            pass

    # Corrente da NEW TOTAL INV (prioritario sull'archivio)
    try:
        current_df_raw = _load_raw_from_content(current_content, current_year)
        current_monthly = _extract_monthly_platform_breakdown(current_df_raw)
        if current_monthly:
            merged_year_data[current_year] = current_monthly
    except Exception:
        pass

    years = sorted(merged_year_data.keys(), key=int)
    rows: list[dict[str, object]] = []

    for year in years:
        month_data = merged_year_data.get(year, {})
        monthly_totals = {month: float(month_data.get(month, {}).get("Totale", 0.0)) for month in MESI}
        details = {
            month: {
                "Bondora": float(month_data.get(month, {}).get("Bondora", 0.0)),
                "Mintos": float(month_data.get(month, {}).get("Mintos", 0.0)),
                "ReLender": float(month_data.get(month, {}).get("ReLender", 0.0)),
            }
            for month in MESI
        }
        annual_total = sum(monthly_totals.values())

        # Include solo anni con almeno un valore numerico valorizzato
        if not any(abs(val) > 1e-9 for val in monthly_totals.values()):
            continue

        rows.append(
            {
                "year": year,
                "monthly_totals": monthly_totals,
                "details": details,
                "annual_total": annual_total,
            }
        )

    return {
        "months": MESI,
        "years": [row["year"] for row in rows],
        "rows": rows,
        "current_year": current_year,
    }


def _find_gt_title_rows(df_raw: pd.DataFrame) -> list[int]:
    """
    Trova le righe titolo delle due tabelle GT_ANNO.
    Priorita': match espliciti su PIATTAFORMA/ANNO e MEDIA 12 M;
    fallback su euristica per retrocompatibilita'.
    """
    first_col = df_raw.iloc[:, 0]

    guadagni_idx = None
    medie_idx = None
    for idx, value in first_col.items():
        text = _normalize_text(value)
        if text == GT_TITLE_GUADAGNI and guadagni_idx is None:
            guadagni_idx = idx
        elif text in {GT_TITLE_MEDIE, "MEDIA 12M"} and medie_idx is None:
            medie_idx = idx

    if guadagni_idx is not None and medie_idx is not None:
        return sorted([guadagni_idx, medie_idx])

    # Fallback: vecchio riconoscimento se i titoli nel file differiscono leggermente
    title_rows: list[int] = []
    for idx, value in first_col.items():
        text = _normalize_text(value)
        if "PIATTAFORMA" in text and ("GUADAG" in text or "MED" in text or "ANNO" in text):
            title_rows.append(idx)

    return sorted(title_rows)[:2]


def _is_real_numeric(value) -> bool:
    if pd.isna(value):
        return False
    if isinstance(value, (int, float)):
        return True

    text = str(value).strip()
    if text == "":
        return False

    # Supporta sia formato 1234.56 che 1.234,56
    normalized = text.replace(" ", "")
    if "," in normalized and "." in normalized:
        normalized = normalized.replace(".", "").replace(",", ".")
    else:
        normalized = normalized.replace(",", ".")

    try:
        float(normalized)
        return True
    except ValueError:
        return False


def _valid_years_from_raw_gt(df_raw: pd.DataFrame, title_rows: list[int]) -> list[str]:
    years: set[str] = set()
    upper_col_limit = min(df_raw.shape[1], 40)

    sorted_titles = sorted(title_rows)
    for idx, title_idx in enumerate(sorted_titles):
        stop_idx = sorted_titles[idx + 1] if idx + 1 < len(sorted_titles) else len(df_raw)

        year_cols: dict[str, int] = {}
        for col_i in range(1, upper_col_limit):
            header_val = df_raw.iloc[title_idx, col_i]
            if _looks_like_year(header_val):
                year_key = str(int(float(header_val)))
                year_cols[year_key] = col_i

        for year_key, col_i in year_cols.items():
            has_numeric = False
            for row_i in range(title_idx + 1, stop_idx):
                label_cell = df_raw.iloc[row_i, 0]
                if pd.isna(label_cell):
                    continue

                label = str(label_cell).strip()
                if label == "":
                    continue
                if label.upper() in {"SOMMA", "TOTALE"}:
                    break

                if _is_real_numeric(df_raw.iloc[row_i, col_i]):
                    has_numeric = True
                    break

            if has_numeric:
                years.add(year_key)

    return sorted(years, key=int)


def get_gt_anno_data(dbx: dropbox.Dropbox) -> dict[str, object]:
    """
    Legge il foglio GT_ANNO e restituisce:
      - tables: {'guadagni': DataFrame, 'medie': DataFrame}
      - years: anni validi con valori numerici nelle celle sottostanti
      - platforms: piattaforme disponibili (senza SOMMA/TOTALE)
      - metrics: mapping etichetta -> chiave tabella
    """
    df_raw = _load_raw(dbx, SHEET_GT_ANNO)
    title_rows = _find_gt_title_rows(df_raw)

    if len(title_rows) < 2:
        raise ValueError("Foglio GT_ANNO non riconosciuto: non trovo le 2 tabelle attese.")

    first_idx, second_idx = title_rows[0], title_rows[1]
    guadagni_df = _extract_gt_table(df_raw, first_idx, second_idx)
    medie_df = _extract_gt_table(df_raw, second_idx, None)

    tables = {
        "guadagni": guadagni_df,
        "medie": medie_df,
    }

    years = _valid_years_from_raw_gt(df_raw, title_rows)

    platforms = []
    for source_df in (guadagni_df, medie_df):
        if source_df is None or source_df.empty:
            continue
        for platform in source_df["Piattaforma"].astype(str).str.strip().tolist():
            if platform.upper() in {"SOMMA", "TOTALE"} or platform == "":
                continue
            if platform not in platforms:
                platforms.append(platform)

    return {
        "tables": tables,
        "years": years,
        "platforms": platforms,
        "metrics": {
            "Media guadagni": "medie",
            "Guadagni totali": "guadagni",
        },
    }


def get_fixed_platform_goals(dbx: dropbox.Dropbox, sheet_anno: str) -> dict[str, float]:
    """
    Estrae i nomi piattaforma fissi da E37/E38 e gli obiettivi da G37/G38.
    Restituisce: {"NomePiattaforma": obiettivo_float}
    """
    df_raw = _load_raw(dbx, sheet_anno)
    goals: dict[str, float] = {}

    for row_idx in _FIXED_PLATFORM_ROWS:
        platform_cell = df_raw.iloc[row_idx, _PLATFORM_COL]
        goal_cell = df_raw.iloc[row_idx, _GOAL_COL]

        if pd.isna(platform_cell):
            continue

        platform = str(platform_cell).strip()
        if platform == "":
            continue

        goals[platform] = _safe_float(goal_cell)

    return goals


def get_fin_inv_debts(dbx: dropbox.Dropbox, sheet_anno: str) -> dict[str, float]:
    """Legge i debiti Fin casa / Fin car dal foglio annuale (celle D44 e D46)."""
    df_raw = _load_raw(dbx, sheet_anno)

    fin_home = _safe_float(df_raw.iloc[_FIN_HOME_ROW, _FIN_VALUE_COL]) if _FIN_HOME_ROW < len(df_raw) else 0.0
    fin_car = _safe_float(df_raw.iloc[_FIN_CAR_ROW, _FIN_VALUE_COL]) if _FIN_CAR_ROW < len(df_raw) else 0.0

    return {
        "fin_home": fin_home,
        "fin_car": fin_car,
        "total": round(fin_home + fin_car, 2),
    }


def get_tables(dbx: dropbox.Dropbox, sheet_anno: str) -> dict[str, pd.DataFrame]:
    """
    Restituisce un dizionario con le 3 tabelle:
      - 'investimenti'
      - 'guadagni'
      - 'inv_guad'
    """
    df_raw = _load_raw(dbx, sheet_anno)
    return {
        "investimenti": _extract_table(df_raw, TITOLI["investimenti"]),
        "guadagni":     _extract_table(df_raw, TITOLI["guadagni"]),
        "inv_guad":     _extract_table(df_raw, TITOLI["inv_guad"]),
    }


def _extract_main_tables_from_raw(df_raw: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {
        "investimenti": _extract_table(df_raw, TITOLI["investimenti"]),
        "guadagni": _extract_table(df_raw, TITOLI["guadagni"]),
        "inv_guad": _extract_table(df_raw, TITOLI["inv_guad"]),
    }


def _has_gains_for_core_platforms(guadagni_df: pd.DataFrame) -> bool:
    if guadagni_df is None or guadagni_df.empty or "Piattaforma" not in guadagni_df.columns:
        return False

    target_aliases = {
        "bondora",
        "mintos",
        "relender",
    }
    month_cols = [col for col in MESI if col in guadagni_df.columns]
    if not month_cols:
        return False

    for _, row in guadagni_df.iterrows():
        norm_platform = _normalize_platform_key(row.get("Piattaforma", ""))
        if norm_platform not in target_aliases:
            continue
        for month in month_cols:
            if abs(float(_safe_float(row.get(month, 0.0)))) > 1e-9:
                return True

    return False


def get_yearly_main_tables_data(dbx: dropbox.Dropbox, current_year_sheet: str) -> dict[str, object]:
    """Restituisce anni selezionabili e tabelle tab principali per anno.

    Fonti:
    - storico: file ARCHIVIO INV (tutti i fogli anno validi)
    - corrente: NEW TOTAL INV (foglio anno corrente, che sovrascrive eventuale stesso anno in archivio)

    Include solo gli anni con almeno un guadagno != 0 su Bondora/Mintos/ReLender.
    """
    merged_sources: dict[str, bytes] = {}

    archive_path = _find_archive_file_path(dbx)
    if archive_path:
        try:
            archive_content = _download_file(dbx, archive_path)
            for year in _extract_year_sheets_from_content(archive_content):
                merged_sources[year] = archive_content
        except Exception:
            pass

    current_content = _download_file(dbx, FILE_PATH)
    merged_sources[str(current_year_sheet)] = current_content

    tables_by_year: dict[str, dict[str, pd.DataFrame]] = {}
    for year in sorted(merged_sources.keys(), key=int):
        content = merged_sources[year]
        try:
            df_raw = _load_raw_from_content(content, year)
            tables = _extract_main_tables_from_raw(df_raw)
            if not _has_gains_for_core_platforms(tables.get("guadagni")):
                continue
            tables_by_year[year] = tables
        except Exception:
            continue

    years = sorted(tables_by_year.keys(), key=int)
    default_year = str(current_year_sheet) if str(current_year_sheet) in tables_by_year else (years[-1] if years else "")

    return {
        "years": years,
        "default_year": default_year,
        "tables_by_year": tables_by_year,
    }


def compute_bondo_evo_target_dates(data: dict[float, dict], base_datetime: datetime | None = None) -> dict[float, dict]:
    """
    Calcola in modo cumulativo la data di raggiungimento per i target non ancora raggiunti.

    Regola:
    - se MTNS < 0: target gia' raggiunto, nessuna data
    - primo target non raggiunto: base_datetime + MDTNS giorni
    - target successivi non raggiunti: data target precedente non raggiunto + MDTNS giorni
    """
    if not data:
        return {}

    anchor_dt = base_datetime or datetime.now()
    enriched: dict[float, dict] = {}

    for daily_value, raw in data.items():
        row = dict(raw)
        mtns = row.get("mtns")
        mdtns = row.get("mdtns")
        is_reached = mtns is not None and float(mtns) < 0

        row["is_reached"] = is_reached
        row["target_date"] = None

        if not is_reached and mdtns is not None:
            # La data target è sempre calcolata a partire dalla data odierna
            target_dt = anchor_dt + timedelta(days=float(mdtns))
            row["target_date"] = target_dt.date()

        enriched[daily_value] = row

    return enriched


def get_bondo_evo_selectable_targets(data: dict[float, dict]) -> list[float]:
    """Restituisce i target selezionabili per Bondora Evolution.

    Regola UI richiesta:
    - mostra solo il target piu' alto gia' raggiunto
    - mostra tutti i target ancora non raggiunti
    """
    if not data:
        return []

    ordered_values = sorted(float(v) for v in data.keys())
    reached_values = [
        value for value in ordered_values
        if bool((data.get(value) or {}).get("is_reached", False))
    ]
    max_reached = max(reached_values) if reached_values else None

    selectable: list[float] = []
    for value in ordered_values:
        row = data.get(value) or {}
        is_reached = bool(row.get("is_reached", False))
        if is_reached:
            if max_reached is not None and value == max_reached:
                selectable.append(value)
        else:
            selectable.append(value)

    return selectable


def get_progressive_amount_targets(current_amount: float, step: float, count: int = 5) -> list[float]:
    """Restituisce i target progressivi successivi in base allo step scelto.

    Esempio: current=2782, step=10 -> [2790, 2800, 2810, 2820, 2830]
    """
    if count <= 0 or step <= 0:
        return []

    first_target = (math.floor(float(current_amount) / float(step)) + 1) * float(step)
    return [round(first_target + i * float(step), 2) for i in range(count)]


def get_euro_milestone_targets(current_amount: float, target_amount: float) -> list[float]:
    """Restituisce ogni soglia intera in euro tra cifra attuale e target.

    Esempio: current=2782.34, target=2790 -> [2783.0, ..., 2790.0]
    """
    current = float(current_amount)
    target = float(target_amount)
    if target <= current:
        return []

    first_euro = int(math.floor(current)) + 1
    last_euro = int(math.floor(target))
    if last_euro < first_euro:
        return []

    return [float(value) for value in range(first_euro, last_euro + 1)]


def get_gpp_anno_data(dbx: dropbox.Dropbox) -> dict[str, object]:
    """
    Legge il foglio GPP_ANNO.
    Struttura reale:
      - Riga 0: col A = nome prima piattaforma, col B..M = mesi abbreviati (GEN..DIC)
      - Righe con anno numerico in col A: dati mensili per la piattaforma corrente
      - Righe con stringa non-anno in col A (es. 'BONDORA', 'MINTOS'): inizio nuovo blocco piattaforma
      - La mappa colonne-mesi è fissa dalla riga 0 per tutte le piattaforme

    Restituisce:
      - platforms: lista nomi piattaforme
      - years: anni validi (con almeno un valore numerico != 0)
      - data: {platform: {year: {mese_completo: valore}}}
    """
    df_raw = _load_raw(dbx, SHEET_GPP_ANNO)
    n_rows, n_cols = df_raw.shape

    # Leggi mappa colonne-mesi dalla riga 0
    col_to_month: dict[int, str] = {}
    for col_i in range(1, min(n_cols, 14)):
        abbr = str(df_raw.iloc[0, col_i]).strip().upper()
        full = MESI_ABBR_TO_FULL.get(abbr)
        if full:
            col_to_month[col_i] = full

    platforms = []
    all_years: set[str] = set()
    data: dict[str, dict[str, dict[str, float]]] = {}

    current_platform: str | None = None

    for row_i in range(n_rows):
        cell = df_raw.iloc[row_i, 0]
        if pd.isna(cell):
            continue

        if _looks_like_year(cell):
            # Riga dati anno
            if current_platform is None:
                continue
            year_key = str(int(float(cell)))
            month_values: dict[str, float] = {}
            has_numeric = False
            for col_i, mese_full in col_to_month.items():
                val = df_raw.iloc[row_i, col_i]
                fval = _safe_float(val)
                month_values[mese_full] = fval
                if _is_real_numeric(val) and fval != 0.0:
                    has_numeric = True
            data[current_platform][year_key] = month_values
            if has_numeric:
                all_years.add(year_key)
        else:
            # Riga intestazione nuova piattaforma
            platform = str(cell).strip()
            if platform == "":
                continue
            current_platform = platform
            if platform not in data:
                platforms.append(platform)
                data[platform] = {}

    return {
        "platforms": platforms,
        "years": sorted(all_years, key=int),
        "data": data,
    }


def get_bondo_evo_daily_values(dbx: dropbox.Dropbox) -> dict:
    """
    Carica il foglio Bondo_Evo e restituisce un dizionario con i dati utili
    per ogni valore giornaliero, arricchiti con lo stato dell'obiettivo e la data target.
    """
    try:
        df_raw = _load_raw(dbx, SHEET_BONDO_EVO)
        # Colonne: 0=Daily, 34=CAP PR, 35=DTNS, 38=MTNS, 39=MDTNS, 40=AMM
        data = {}

        for idx in range(1, 112):
            if idx < len(df_raw):
                daily_val = df_raw.iloc[idx, 0]

                if pd.isna(daily_val):
                    continue

                try:
                    daily_float = _safe_float(daily_val)
                    cap_pr = _safe_float(df_raw.iloc[idx, 34])
                    dtns = _safe_float(df_raw.iloc[idx, 35])
                    mtns = _safe_float(df_raw.iloc[idx, 38])
                    mdtns = _safe_float(df_raw.iloc[idx, 39]) if pd.notna(df_raw.iloc[idx, 39]) else None
                    amm = _safe_float(df_raw.iloc[idx, 40]) if pd.notna(df_raw.iloc[idx, 40]) else None

                    data[daily_float] = {
                        "cap_pr": cap_pr,
                        "dtns": dtns,
                        "mtns": mtns,
                        "mdtns": mdtns,
                        "amm": amm,
                    }
                except (ValueError, TypeError):
                    pass

        return compute_bondo_evo_target_dates(data)
    except Exception:
        return {}
