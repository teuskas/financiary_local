"""Data reader: parse financial CSV files into a normalised pandas DataFrame."""

import io
import os
from pathlib import Path
from typing import Iterable

import pandas as pd


# Default column names expected in the CSV files.  They can be overridden via
# environment variables so users don't have to rename their existing files.
_DEFAULT_COLUMNS = {
    "date": os.environ.get("CSV_DATE_COLUMN", "date"),
    "amount": os.environ.get("CSV_AMOUNT_COLUMN", "amount"),
    "description": os.environ.get("CSV_DESCRIPTION_COLUMN", "description"),
    "category": os.environ.get("CSV_CATEGORY_COLUMN", "category"),
}

REQUIRED_COLUMNS = {"date", "amount"}


class DataReaderError(Exception):
    """Raised when a CSV file cannot be parsed."""


def _column_map() -> dict[str, str]:
    """Return a mapping from user-supplied column names to canonical names."""
    return {
        os.environ.get("CSV_DATE_COLUMN", "date"): "date",
        os.environ.get("CSV_AMOUNT_COLUMN", "amount"): "amount",
        os.environ.get("CSV_DESCRIPTION_COLUMN", "description"): "description",
        os.environ.get("CSV_CATEGORY_COLUMN", "category"): "category",
    }


def parse_csv(raw: bytes, source_name: str = "<unknown>") -> pd.DataFrame:
    """Parse *raw* CSV bytes and return a normalised DataFrame.

    The returned DataFrame always has at least the columns ``date`` and
    ``amount``.  Optional columns ``description`` and ``category`` are
    included when present in the source file.

    Parameters
    ----------
    raw:
        Raw CSV bytes (e.g. as downloaded from Dropbox).
    source_name:
        A label used in error messages (e.g. the Dropbox path).

    Returns
    -------
    pd.DataFrame
        Normalised DataFrame with canonical column names and typed values.
    """
    try:
        df = pd.read_csv(io.BytesIO(raw))
    except Exception as exc:
        raise DataReaderError(f"Cannot read CSV '{source_name}': {exc}") from exc

    # Normalise column names: strip whitespace, lower-case.
    df.columns = [str(c).strip().lower() for c in df.columns]

    # Rename user-defined column names to canonical names.
    col_map = {k.lower(): v for k, v in _column_map().items()}
    df = df.rename(columns=col_map)

    # Validate required columns are present.
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise DataReaderError(
            f"CSV '{source_name}' is missing required columns: {sorted(missing)}. "
            f"Found columns: {list(df.columns)}. "
            "Set CSV_DATE_COLUMN / CSV_AMOUNT_COLUMN environment variables if your "
            "file uses different header names."
        )

    # Type coercion.
    df["date"] = pd.to_datetime(df["date"], format="mixed", dayfirst=True, errors="coerce")
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")

    # Drop rows where mandatory fields failed to parse.
    before = len(df)
    df = df.dropna(subset=["date", "amount"])
    dropped = before - len(df)
    if dropped:
        import warnings

        warnings.warn(
            f"'{source_name}': dropped {dropped} row(s) with unparseable date or amount.",
            stacklevel=2,
        )

    df = df.sort_values("date").reset_index(drop=True)
    return df


def load_dataframes(
    csv_items: Iterable[tuple[str, bytes]],
) -> pd.DataFrame:
    """Concatenate multiple CSV files into a single DataFrame.

    Parameters
    ----------
    csv_items:
        An iterable of ``(name, raw_bytes)`` pairs – e.g. the output of
        :meth:`~src.dropbox_client.DropboxClient.iter_csv_contents`.

    Returns
    -------
    pd.DataFrame
        Combined DataFrame sorted by date.  Returns an empty DataFrame if
        *csv_items* contains no parseable files.
    """
    frames: list[pd.DataFrame] = []
    for name, raw in csv_items:
        try:
            frames.append(parse_csv(raw, source_name=name))
        except DataReaderError as exc:
            import warnings

            warnings.warn(str(exc), stacklevel=2)

    if not frames:
        return pd.DataFrame(columns=["date", "amount"])

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.sort_values("date").reset_index(drop=True)
    return combined
