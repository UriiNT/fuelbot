"""FuelBot — Mobile Edition (pure Kivy, no KivyMD).

Запуск на десктопе:  python kivy_app.py
Сборка APK:         buildozer android debug
"""

import datetime
import json
import os
import sys
import threading
import urllib3

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp, sp
from kivy.properties import NumericProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gazpromneft import GazpromneftClient, fuel_label as gpn_fuel_label
from lukoil import LukoilClient

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BG = [15 / 255, 21 / 255, 34 / 255, 1]
BG_CARD = [26 / 255, 35 / 255, 50 / 255, 1]
BG_INPUT = [35 / 255, 45 / 255, 65 / 255, 1]
ACCENT = [47 / 255, 111 / 255, 237 / 255, 1]
GREEN = [63 / 255, 214 / 255, 139 / 255, 1]
RED = [255 / 255, 107 / 255, 107 / 255, 1]
GREY = [139 / 255, 148 / 255, 167 / 255, 1]
FG = [232 / 255, 237 / 255, 245 / 255, 1]
FG_DIM = [160 / 255, 170 / 255, 190 / 255, 1]
HEADER_BG = [39 / 255, 64 / 255, 96 / 255, 1]
GREEN_BG = [63 / 255, 214 / 255, 139 / 255, 0.15]
RED_BG = [255 / 255, 107 / 255, 107 / 255, 0.15]
GREY_BG = [139 / 255, 148 / 255, 167 / 255, 0.08]

SETTINGS_FILE = "fuelbot_settings.json"


class FuelBotApp(App):
    city_text = StringProperty("Нижний Тагил")
    status_text = StringProperty("Загрузка...")
    last_update = StringProperty("")
    active_tab = NumericProperty(0)

    def build(self):
        self.title = "Наличие топлива на АЗС"
        self._load_settings()
        self.gpn_client = GazpromneftClient()
        self.lukoil_client = LukoilClient()
        self._gen = 0
        self._gpn_box = None
        self._lukoil_box = None

        Window.clearcolor = BG
        if sys.platform != "android":
            Window.size = (420, 780)

        root = BoxLayout(orientation="vertical", spacing=0, padding=0)

        header = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(48),
            padding=[dp(14), dp(8)],
        )
        with header.canvas.before:
            from kivy.graphics import Color, Rectangle
            Color(*HEADER_BG)
            header._bg = Rectangle(pos=header.pos, size=header.size)
            header.bind(pos=lambda inst, val: setattr(inst._bg, "pos", val))
            header.bind(size=lambda inst, val: setattr(inst._bg, "size", val))
        header.add_widget(Label(
            text="Наличие топлива на АЗС",
            font_size=sp(16),
            color=FG,
            bold=True,
            halign="left",
            valign="middle",
            size_hint_x=0.7,
        ))
        self._last_lbl = Label(
            text="",
            font_size=sp(10),
            color=ACCENT,
            halign="right",
            valign="middle",
            size_hint_x=0.3,
        )
        header.add_widget(self._last_lbl)
        root.add_widget(header)

        input_row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(52),
            padding=[dp(10), dp(4)],
            spacing=dp(8),
        )
        self._city_input = TextInput(
            text=self.city_text,
            hint_text="Город",
            font_size=sp(15),
            size_hint_x=0.7,
            multiline=False,
            background_normal="",
            background_active="",
            background_color=BG_INPUT,
            foreground_color=FG,
            hint_text_color=GREY,
            cursor_color=ACCENT,
            padding=[dp(10), dp(8)],
        )
        self._city_input.bind(text=self._on_city)
        input_row.add_widget(self._city_input)

        btn_refresh = Button(
            text="Обновить",
            font_size=sp(13),
            size_hint_x=0.3,
            background_normal="",
            background_color=ACCENT,
            color=FG,
            bold=True,
        )
        btn_refresh.bind(on_press=lambda _: self.refresh())
        input_row.add_widget(btn_refresh)
        root.add_widget(input_row)

        tab_bar = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(42),
            padding=[dp(4), dp(2)],
            spacing=dp(4),
        )
        self._tab_gpn_btn = Button(
            text="Газпромнефть",
            font_size=sp(13),
            background_normal="",
            background_color=ACCENT,
            color=FG,
            bold=True,
        )
        self._tab_gpn_btn.bind(on_press=lambda _: self._switch_tab(0))
        tab_bar.add_widget(self._tab_gpn_btn)

        self._tab_lukoil_btn = Button(
            text="Лукойл",
            font_size=sp(13),
            background_normal="",
            background_color=HEADER_BG,
            color=GREY,
        )
        self._tab_lukoil_btn.bind(on_press=lambda _: self._switch_tab(1))
        tab_bar.add_widget(self._tab_lukoil_btn)
        root.add_widget(tab_bar)

        self._content_area = BoxLayout(orientation="vertical", spacing=0, padding=0)

        self._gpn_sv = ScrollView(
            do_scroll_x=False,
            bar_color=ACCENT,
            bar_width=dp(3),
            scroll_type=["bars", "content"],
        )
        self._gpn_box = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            padding=dp(8),
            spacing=dp(8),
        )
        self._gpn_box.bind(minimum_height=self._gpn_box.setter("height"))
        self._gpn_sv.add_widget(self._gpn_box)

        self._lukoil_sv = ScrollView(
            do_scroll_x=False,
            bar_color=ACCENT,
            bar_width=dp(3),
            scroll_type=["bars", "content"],
        )
        self._lukoil_box = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            padding=dp(8),
            spacing=dp(8),
        )
        self._lukoil_box.bind(minimum_height=self._lukoil_box.setter("height"))
        self._lukoil_sv.add_widget(self._lukoil_box)

        self._content_area.add_widget(self._gpn_sv)
        root.add_widget(self._content_area)

        status_bar = BoxLayout(
            size_hint_y=None,
            height=dp(28),
            padding=[dp(14), dp(4)],
        )
        self._status_lbl = Label(
            text=self.status_text,
            font_size=sp(11),
            color=GREY,
            halign="center",
        )
        status_bar.add_widget(self._status_lbl)
        root.add_widget(status_bar)

        Clock.schedule_once(lambda _: self.refresh(), 0.5)

        return root

    def _on_city(self, inst, val):
        self.city_text = val

    def _settings_path(self):
        path = os.path.join(self.user_data_dir, SETTINGS_FILE)
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
        except OSError:
            pass
        return path

    def _load_settings(self):
        try:
            path = self._settings_path()
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            city = str(data.get("city", "")).strip()
            if city:
                self.city_text = city
        except (OSError, ValueError, TypeError):
            pass

    def _save_settings(self):
        try:
            path = self._settings_path()
            data = {
                "city": self.city_text.strip(),
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def on_stop(self):
        self._save_settings()

    def _switch_tab(self, idx):
        self.active_tab = idx
        parent = self._content_area
        active = self._gpn_sv if idx == 0 else self._lukoil_sv
        inactive = self._lukoil_sv if idx == 0 else self._gpn_sv

        if idx == 0:
            self._tab_gpn_btn.background_color = ACCENT
            self._tab_gpn_btn.color = FG
            self._tab_lukoil_btn.background_color = HEADER_BG
            self._tab_lukoil_btn.color = GREY
        else:
            self._tab_lukoil_btn.background_color = ACCENT
            self._tab_lukoil_btn.color = FG
            self._tab_gpn_btn.background_color = HEADER_BG
            self._tab_gpn_btn.color = GREY

        parent.remove_widget(inactive)
        if active.parent is None:
            parent.add_widget(active)

    def refresh(self):
        self.status_text = "Загрузка..."
        if hasattr(self, "_status_lbl"):
            self._status_lbl.text = self.status_text
        self._save_settings()
        self._gen += 1
        gen = self._gen
        city = (self.city_text or "").strip().lower() or "тагил"
        threading.Thread(target=self._fetch, args=(city, gen), daemon=True).start()

    def _fetch(self, city, gen):
        gpn_stations, lukoil_stations = [], []
        gpn_err, lukoil_err = "", ""
        try:
            gpn_stations = self.gpn_client.enrich_with_prices(
                self.gpn_client.get_stations_by_city(city)
            )
        except Exception as exc:
            gpn_err = str(exc)
        try:
            lukoil_stations = self.lukoil_client.get_stations_by_city(city)
        except Exception as exc:
            lukoil_err = str(exc)
        Clock.schedule_once(
            lambda _: self._render(gen, gpn_stations, lukoil_stations, gpn_err, lukoil_err), 0
        )

    def _render(self, gen, gpn_stations, lukoil_stations, gpn_err, lukoil_err):
        if gen != self._gen:
            return

        now = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
        self.last_update = now
        self._last_lbl.text = now

        self._gpn_box.clear_widgets()
        self._lukoil_box.clear_widgets()

        if gpn_err:
            self._gpn_box.add_widget(self._error_card(f"Ошибка: {gpn_err}"))
        elif not gpn_stations:
            self._gpn_box.add_widget(self._error_card("АЗС не найдены"))
        else:
            all_fuels = set()
            for st in gpn_stations:
                all_fuels.update(st.fuels.keys())
            fuel_ids = sorted(all_fuels)
            labels = [gpn_fuel_label(fid) for fid in fuel_ids]
            for idx, st in enumerate(gpn_stations):
                self._gpn_box.add_widget(self._gpn_card(idx + 1, st, fuel_ids, labels))

        if lukoil_err:
            self._lukoil_box.add_widget(self._error_card(f"Ошибка: {lukoil_err}"))
        elif not lukoil_stations:
            self._lukoil_box.add_widget(self._error_card("АЗС не найдены"))
        else:
            all_fuel_names = set()
            for st in lukoil_stations:
                for name, _ in st.fuels:
                    all_fuel_names.add(name)
            fuel_names = sorted(all_fuel_names)
            for idx, st in enumerate(lukoil_stations):
                self._lukoil_box.add_widget(self._lukoil_card(idx + 1, st, fuel_names))

        parts = []
        if gpn_stations:
            parts.append(f"ГПН: {len(gpn_stations)}")
        if lukoil_stations:
            parts.append(f"ЛК: {len(lukoil_stations)}")
        self.status_text = f"Найдено: {', '.join(parts)}" if parts else "Ничего не найдено"
        self._status_lbl.text = self.status_text

    def _error_card(self, text):
        card = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            height=dp(70),
            padding=dp(16),
        )
        with card.canvas.before:
            from kivy.graphics import Color, RoundedRectangle
            Color(*RED_BG)
            card._bg_rect = RoundedRectangle(
                pos=card.pos, size=card.size, radius=[dp(12)]
            )
            card.bind(pos=lambda inst, val: setattr(card._bg_rect, "pos", val))
            card.bind(size=lambda inst, val: setattr(card._bg_rect, "size", val))
        card.add_widget(Label(
            text=text, font_size=sp(14), color=RED,
            halign="center", valign="middle",
        ))
        return card

    def _station_card(self, idx, station, fuel_items):
        n_fuel = len(fuel_items)
        h = dp(64) + dp(28) * n_fuel

        card = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            height=h,
            padding=dp(12),
            spacing=dp(1),
        )
        with card.canvas.before:
            from kivy.graphics import Color, RoundedRectangle
            Color(*BG_CARD)
            card._bg_rect = RoundedRectangle(
                pos=card.pos, size=card.size, radius=[dp(10)]
            )
            card.bind(pos=lambda inst, val: setattr(card._bg_rect, "pos", val))
            card.bind(size=lambda inst, val: setattr(card._bg_rect, "size", val))

        title = station.name or ""
        num = station.number or ""
        if num:
            title += f"  [{num}]"
        card.add_widget(Label(
            text=f"{idx}. {title}",
            font_size=sp(14), color=FG, bold=True,
            halign="left", valign="middle",
            size_hint_y=None, height=dp(26),
            text_size=(None, None),
        ))
        card.add_widget(Label(
            text=station.address or "-",
            font_size=sp(11), color=FG_DIM,
            halign="left", valign="middle",
            size_hint_y=None, height=dp(20),
        ))

        for label_text, available, price_str in fuel_items:
            row = BoxLayout(
                orientation="horizontal",
                size_hint_y=None,
                height=dp(28),
                padding=[dp(6), dp(1)],
            )
            with row.canvas.before:
                from kivy.graphics import Color, RoundedRectangle
                if available is True:
                    Color(*GREEN_BG)
                elif available is False:
                    Color(*RED_BG)
                else:
                    Color(*GREY_BG)
                row._bg_rect = RoundedRectangle(
                    pos=row.pos, size=row.size, radius=[dp(4)]
                )
                row.bind(pos=lambda inst, val: setattr(inst._bg_rect, "pos", val))
                row.bind(size=lambda inst, val: setattr(inst._bg_rect, "size", val))

            if available is True:
                dot_color = GREEN
                status = "Есть"
            elif available is False:
                dot_color = RED
                status = "Нет"
            else:
                dot_color = GREY
                status = "—"

            status_text = status
            if price_str and available is not False:
                status_text = f"{status}  {price_str}"

            row.add_widget(Label(
                text=f" {label_text}",
                font_size=sp(12), color=dot_color,
                halign="left", valign="middle",
                size_hint_x=0.55,
                bold=available is True,
            ))
            row.add_widget(Label(
                text=status_text,
                font_size=sp(11),
                color=dot_color if available is not False else RED,
                halign="right", valign="middle",
                size_hint_x=0.45,
            ))
            card.add_widget(row)

        return card

    def _gpn_card(self, idx, station, fuel_ids, labels):
        items = []
        for i, fid in enumerate(fuel_ids):
            val = station.fuels.get(fid)
            price = station.fuel_prices.get(fid)
            price_str = self._fmt_price(price)
            items.append((labels[i], val, price_str))
        return self._station_card(idx, station, items)

    def _lukoil_card(self, idx, station, fuel_names):
        fuel_map = {name: price for name, price in station.fuels}
        items = []
        for name in fuel_names:
            price = fuel_map.get(name)
            has_fuel = name in fuel_map
            price_str = self._fmt_price(price) if price else None
            items.append((name, has_fuel if has_fuel else None, price_str))
        return self._station_card(idx, station, items)

    @staticmethod
    def _fmt_price(price):
        if price is None:
            return None
        try:
            val = float(str(price).replace(",", "."))
            return f"{val:.2f}".rstrip("0").rstrip(".") + " руб."
        except (TypeError, ValueError):
            return None


if __name__ == "__main__":
    FuelBotApp().run()
