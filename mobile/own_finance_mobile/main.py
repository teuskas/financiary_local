"""Own Finance Mobile - Android APK entry point (Kivy)."""

from __future__ import annotations

import threading

from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner

from dropbox_api_mobile import DropboxApiClient, DropboxCreds
from excel_parser_mobile import table_to_text

try:
    from embedded_creds import (  # type: ignore
        DROPBOX_APP_KEY,
        DROPBOX_APP_SECRET,
        DROPBOX_REFRESH_TOKEN,
    )
except Exception:  # noqa: BLE001
    DROPBOX_APP_KEY = ""
    DROPBOX_APP_SECRET = ""
    DROPBOX_REFRESH_TOKEN = ""

TITOLI = {
    "investimenti": "INVESTIMENTI PER PIATTAFORMA",
    "guadagni": "GUADAGNI PER PIATTAFORMA",
    "inv_guad": "INV+GUAD PER PIATTAFORMA",
}

DROPBOX_XLSX_PATH = "/me/new total inv.xlsx"


class OwnFinanceMobileApp(App):
    def build(self):
        self.title = "Own Finance Mobile"
        self.tables: dict[str, list[dict]] = {}
        self.current_year: str = "-"
        self.embedded_creds = self._get_embedded_credentials()

        root = BoxLayout(orientation="vertical", spacing=8, padding=10)

        header_box = BoxLayout(orientation="vertical", size_hint_y=None, height=74, spacing=4)
        header_box.add_widget(Label(text="Own Finance Mobile", size_hint_y=None, height=34))
        header_message = (
            "Accesso Dropbox integrato nell'app"
            if self.embedded_creds is not None
            else "Questa build APK non include credenziali Dropbox"
        )
        header_box.add_widget(Label(text=header_message, size_hint_y=None, height=24))

        controls = BoxLayout(orientation="horizontal", size_hint_y=None, height=44, spacing=8)
        self.refresh_btn = Button(text="Aggiorna dati")
        self.refresh_btn.bind(on_release=lambda *_: self.refresh_data())

        self.table_spinner = Spinner(
            text="investimenti",
            values=("investimenti", "guadagni", "inv_guad"),
            size_hint_x=0.55,
        )
        self.table_spinner.bind(text=lambda *_: self._refresh_table_text())

        controls.add_widget(self.refresh_btn)
        controls.add_widget(self.table_spinner)

        self.status_label = Label(
            text="Avvio in corso..." if self.embedded_creds is not None else "Build APK non configurata",
            size_hint_y=None,
            height=30,
        )

        self.output_label = Label(
            text="",
            halign="left",
            valign="top",
            size_hint_y=None,
        )
        self.output_label.bind(texture_size=self._sync_output_height)
        self.output_label.bind(size=self._sync_output_text_width)

        scroll = ScrollView()
        scroll.add_widget(self.output_label)

        root.add_widget(header_box)
        root.add_widget(controls)
        root.add_widget(self.status_label)
        root.add_widget(scroll)

        self._refresh_table_text()
        if self.embedded_creds is not None:
            Clock.schedule_once(lambda _dt: self.refresh_data(), 0.2)
        return root

    def _sync_output_height(self, instance, value):
        instance.height = max(value[1] + 20, 400)

    def _sync_output_text_width(self, instance, _value):
        instance.text_size = (instance.width - 20, None)

    def _get_embedded_credentials(self) -> DropboxCreds | None:
        if not all([DROPBOX_APP_KEY, DROPBOX_APP_SECRET, DROPBOX_REFRESH_TOKEN]):
            return None
        return DropboxCreds(
            app_key=DROPBOX_APP_KEY,
            app_secret=DROPBOX_APP_SECRET,
            refresh_token=DROPBOX_REFRESH_TOKEN,
        )

    def refresh_data(self):
        if self.embedded_creds is None:
            self.status_label.text = "Credenziali Dropbox non incluse in questa APK"
            return

        self.refresh_btn.disabled = True
        self.status_label.text = "Caricamento da Dropbox in corso..."

        threading.Thread(target=self._refresh_data_worker, args=(self.embedded_creds,), daemon=True).start()

    def _refresh_data_worker(self, creds: DropboxCreds):
        try:
            # Import lazy: evita crash all'avvio se una dipendenza parser manca nel pacchetto.
            from excel_parser_mobile import (
                detect_current_year_sheet_from_bytes,
                extract_tables_from_bytes,
            )

            client = DropboxApiClient(creds)
            content = client.download_file(DROPBOX_XLSX_PATH)
            year = detect_current_year_sheet_from_bytes(content)
            tables = extract_tables_from_bytes(content, sheet_name=year)
        except Exception as exc:  # noqa: BLE001
            Clock.schedule_once(lambda _dt: self._on_refresh_error(str(exc)))
            return

        Clock.schedule_once(lambda _dt: self._on_refresh_success(year, tables))

    def _on_refresh_success(self, year: str, tables: dict[str, list[dict]]):
        self.current_year = year
        self.tables = tables
        self.refresh_btn.disabled = False
        self.status_label.text = f"Dati caricati dal foglio {year}"
        self._refresh_table_text()

    def _on_refresh_error(self, message: str):
        self.refresh_btn.disabled = False
        self.status_label.text = f"Errore: {message[:140]}"

    def _refresh_table_text(self):
        selected = self.table_spinner.text
        rows = self.tables.get(selected, [])
        title = TITOLI.get(selected, selected.upper())
        body = table_to_text(rows)
        self.output_label.text = f"{title} (foglio {self.current_year})\n\n{body}"


def main():
    OwnFinanceMobileApp().run()


if __name__ == "__main__":
    main()

