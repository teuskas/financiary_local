# financiary_local

A standalone Python CLI tool that connects to your **Dropbox** account, reads
financial CSV files, and prints a detailed statistics report.

---

## Features

| Statistic | Description |
|---|---|
| **Overall summary** | Total income, total expenses, net balance, transaction count and date range |
| **By category** | Income, expenses and net balance grouped by category, sorted by largest outflow |
| **Monthly breakdown** | Income, expenses and net balance per calendar month |
| **Monthly averages** | Average monthly income, expenses and net balance |
| **Top expenses** | The N largest single expenses (configurable, default 10) |

---

## Requirements

* Python ≥ 3.12
* A [Dropbox App](https://www.dropbox.com/developers/apps) with an **Access Token**

---

## Quick start

```bash
# 1. Clone and enter the repository
git clone https://github.com/teuskas/financiary_local.git
cd financiary_local

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure your credentials
cp .env.example .env
# Edit .env and set DROPBOX_ACCESS_TOKEN and DROPBOX_FOLDER_PATH

# 4. Run the tool
python -m src.main
```

---

## Configuration

All configuration is done via environment variables (or a `.env` file in the
project root).

| Variable | Required | Default | Description |
|---|---|---|---|
| `DROPBOX_ACCESS_TOKEN` | ✅ | – | Dropbox OAuth2 access token |
| `DROPBOX_FOLDER_PATH` | | `/` | Dropbox folder to scan for CSV files |
| `CSV_DATE_COLUMN` | | `date` | Name of the date column in your CSV files |
| `CSV_AMOUNT_COLUMN` | | `amount` | Name of the amount column in your CSV files |
| `CSV_DESCRIPTION_COLUMN` | | `description` | Name of the description column |
| `CSV_CATEGORY_COLUMN` | | `category` | Name of the category column |

### Generating a Dropbox Access Token

1. Go to [https://www.dropbox.com/developers/apps](https://www.dropbox.com/developers/apps).
2. Click **Create app** → choose *Scoped access* → *Full Dropbox*.
3. In the **Permissions** tab, enable `files.content.read`.
4. In the **Settings** tab, under *OAuth 2*, click **Generate** to create an
   access token.
5. Copy it into your `.env` file.

---

## CSV file format

The tool reads every `.csv` file found (recursively) inside
`DROPBOX_FOLDER_PATH`.  Files must contain at minimum a **date** column and an
**amount** column.  Positive amounts are treated as *income*; negative amounts
as *expenses*.

### Minimal example

```csv
date,amount
2024-01-05,1500.00
2024-01-10,-200.00
2024-01-15,-50.00
```

### Full example (with optional columns)

```csv
date,amount,description,category
2024-01-05,1500.00,Salary,income
2024-01-10,-200.00,Rent,housing
2024-01-15,-50.00,Groceries,food
2024-02-05,1500.00,Salary,income
2024-02-20,-300.00,Utilities,utilities
```

Supported date formats include `YYYY-MM-DD`, `DD/MM/YYYY` and most other
unambiguous formats.  European (day-first) ordering is assumed for ambiguous
formats.

---

## CLI options

```
python -m src.main [--folder PATH] [--top N]

  --folder PATH   Dropbox folder to scan (overrides DROPBOX_FOLDER_PATH)
  --top N         Number of top expenses to display (default: 10)
```

---

## Running tests

```bash
pip install -r requirements.txt
python -m pytest tests/ -v
```

---

## Project structure

```
financiary_local/
├── requirements.txt          # Python dependencies
├── .env.example              # Template for environment variables
├── src/
│   ├── dropbox_client.py     # Dropbox authentication and file retrieval
│   ├── data_reader.py        # CSV parsing and DataFrame normalisation
│   ├── statistics.py         # Financial statistics calculations
│   └── main.py               # CLI entry point
└── tests/
    ├── test_data_reader.py   # Unit tests for data_reader
    └── test_statistics.py    # Unit tests for statistics
```