import io
import dropbox
import pandas as pd


SUPPORTED_EXTENSIONS = [".csv", ".xlsx", ".xls"]


def is_supported(filename: str) -> bool:
    return any(filename.lower().endswith(ext) for ext in SUPPORTED_EXTENSIONS)


def read_file(dbx: dropbox.Dropbox, path: str) -> pd.DataFrame:
    """
    Scarica un file da Dropbox e lo restituisce come DataFrame pandas.
    Supporta CSV, XLSX, XLS.

    Args:
        dbx:  client Dropbox autenticato
        path: percorso del file su Dropbox

    Returns:
        DataFrame con il contenuto del file
    """
    _, response = dbx.files_download(path)
    content = response.content

    if path.lower().endswith(".csv"):
        df = pd.read_csv(io.BytesIO(content))
    elif path.lower().endswith((".xlsx", ".xls")):
        df = pd.read_excel(io.BytesIO(content))
    else:
        raise ValueError(f"Formato non supportato: {path}")

    print(f"[OK] Letto: {path}  →  {len(df)} righe, {df.shape[1]} colonne")
    return df


def read_all_files(dbx: dropbox.Dropbox, entries: list[dict]) -> dict[str, pd.DataFrame]:
    """
    Legge tutti i file supportati dalla lista di entries e li restituisce
    come dizionario { path: DataFrame }.

    Args:
        dbx:     client Dropbox autenticato
        entries: lista restituita da explorer.list_folder()

    Returns:
        Dizionario con path come chiave e DataFrame come valore
    """
    dataframes = {}
    supported_files = [e for e in entries if e["type"] == "file" and is_supported(e["name"])]

    if not supported_files:
        print("[WARN] Nessun file CSV/XLSX trovato.")
        return dataframes

    for entry in supported_files:
        try:
            df = read_file(dbx, entry["path"])
            dataframes[entry["path"]] = df
        except Exception as ex:
            print(f"[ERR] Impossibile leggere {entry['path']}: {ex}")

    return dataframes

