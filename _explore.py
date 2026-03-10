from auth import get_dropbox_client
import pandas as pd
import io

dbx = get_dropbox_client()
_, response = dbx.files_download('/me/new total inv.xlsx')
content = response.content

xl = pd.ExcelFile(io.BytesIO(content))
print('Fogli disponibili:', xl.sheet_names)

# Leggo il foglio 2026 grezzo per capire la struttura
df_raw = pd.read_excel(io.BytesIO(content), sheet_name='2026', header=None)
print('\nPrime 60 righe del foglio 2026:')
print(df_raw.head(60).to_string())

