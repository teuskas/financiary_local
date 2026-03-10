from auth import get_dropbox_client
from explorer import list_folder, print_tree
from reader import read_all_files


def main():
    # 1. Autenticazione
    dbx = get_dropbox_client()

    # 2. Lettura struttura Dropbox (root = "")
    print("\n[INFO] Lettura struttura Dropbox...")
    entries = list_folder(dbx, path="")
    print_tree(entries)

    # 3. Lettura file supportati
    print("\n[INFO] Lettura file CSV/XLSX...")
    dataframes = read_all_files(dbx, entries)

    if not dataframes:
        print("[WARN] Nessun dato letto. Controlla i file nel tuo Dropbox.")
        return

    # 4. Riepilogo dati letti
    print(f"\n[INFO] File letti con successo: {len(dataframes)}")
    for path, df in dataframes.items():
        print(f"  - {path}: {len(df)} righe x {df.shape[1]} colonne")

    # --- prossimo step: statistiche ---


if __name__ == "__main__":
    main()

