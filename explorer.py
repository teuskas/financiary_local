import dropbox
import dropbox.files


def list_folder(dbx: dropbox.Dropbox, path: str = "") -> list[dict]:
    """
    Legge ricorsivamente il contenuto di una cartella Dropbox.
    Restituisce una lista di dizionari con info su ogni voce.

    Args:
        dbx:  client Dropbox autenticato
        path: percorso della cartella (es. "/dati"), stringa vuota = root

    Returns:
        Lista di dict con chiavi: name, path, type, size (solo per file)
    """
    entries = []
    result = dbx.files_list_folder(path, recursive=True)

    while True:
        for entry in result.entries:
            item = {
                "name": entry.name,
                "path": entry.path_lower,
                "type": "file" if isinstance(entry, dropbox.files.FileMetadata) else "folder",
            }
            if isinstance(entry, dropbox.files.FileMetadata):
                item["size"] = entry.size
                item["modified"] = str(entry.server_modified)
            entries.append(item)

        if not result.has_more:
            break

        result = dbx.files_list_folder_continue(result.cursor)

    return entries


def print_tree(entries: list[dict]) -> None:
    """Stampa l'elenco di file/cartelle in modo leggibile."""
    folders = [e for e in entries if e["type"] == "folder"]
    files   = [e for e in entries if e["type"] == "file"]

    print(f"\n{'='*50}")
    print(f"  Cartelle trovate: {len(folders)}")
    print(f"  File trovati:     {len(files)}")
    print(f"{'='*50}\n")

    for item in sorted(entries, key=lambda x: x["path"]):
        prefix = "📁" if item["type"] == "folder" else "📄"
        size   = f"  ({item['size']} bytes)" if item["type"] == "file" else ""
        print(f"{prefix} {item['path']}{size}")

