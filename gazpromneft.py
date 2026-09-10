import datetime
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Optional

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

STATIONS_API = "https://gpnbonus.ru/api/stations/list"
STATION_API = "https://gpnbonus.ru/api/stations/"

# Маппинг id топлива -> "человеческое" название
FUEL_NAMES = {
    1: "ДТ летнее",
    12: "АИ-95",
    21: "АИ-98",
    61: "А-76/80",
    62: "АИ-92",
    372: "ДТ зимнее",
    373: "Газ",
    374: "ДТ",
    421: "АИ-95 G-Drive",
    422: "АИ-98 G-Drive",
    424: "ДТ G-Drive",
    431: "АИ-92 G-Drive",
    461: "ДТ",
    511: "ДТ зимнее G-Drive",
    512: "ДТ",
    531: "Газ",
    541: "ДТ Арктика",
    100032: "АИ-100 G-Drive",
    100036: "АИ-100",
}

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Referer": "https://gpnbonus.ru/fuel/refuel-map",
}


@dataclass
class GPNStation:
    station_id: int
    gpna_id: int
    number: str
    name: str
    address: str
    city: str
    latitude: float
    longitude: float
    work_mode: str
    is_open: bool
    fuels: dict = field(default_factory=dict)  # {fuel_id(int): bool|None}
    fuel_prices: dict = field(default_factory=dict)  # {fuel_id(int): float|None}


class GazpromneftClient:
    def __init__(self, timeout: int = 30):
        self.session = requests.Session()
        self.session.verify = False
        self.session.headers.update(DEFAULT_HEADERS)
        self.timeout = timeout

    def fetch_all(self) -> list:
        """Запрашивает список всех АЗС и возвращает их."""
        try:
            resp = self.session.post(STATIONS_API, json={}, timeout=self.timeout)
            resp.encoding = "utf-8"
            resp.raise_for_status()
            data = resp.json()
        except (requests.RequestException, ValueError) as exc:
            raise RuntimeError(f"Газпромнефть: ошибка запроса к API: {exc}") from exc

        stations = []
        for item in data.get("stations", []):
            fuels = {}
            raw_oils = item.get("oils") or {}
            for fuel_id, available in raw_oils.items():
                try:
                    fuels[int(fuel_id)] = available
                except (TypeError, ValueError):
                    continue
            stations.append(
                GPNStation(
                    station_id=item.get("id") or item.get("GPNAZSID"),
                    gpna_id=item.get("GPNAZSID") or item.get("id"),
                    number=item.get("PNPONumber", ""),
                    name=item.get("name", ""),
                    address=item.get("address", ""),
                    city=item.get("city", ""),
                    latitude=float(item.get("latitude") or 0),
                    longitude=float(item.get("longitude") or 0),
                    work_mode=item.get("workMode", ""),
                    is_open=bool(item.get("open", False)),
                    fuels=fuels,
                )
            )
        return stations

    def get_stations_by_city(self, city_fragment: str = "тагил") -> list:
        """Возвращает АЗС, у которых в названии города есть фрагмент."""
        needle = city_fragment.lower()
        return [st for st in self.fetch_all() if needle in st.city.lower()]

    def _fetch_station_prices(self, gpna_id: int) -> dict:
        """Получает цены и актуальное наличие для одной АЗС."""
        resp = self.session.post(
            f"{STATION_API}{gpna_id}", json={}, timeout=self.timeout
        )
        resp.encoding = "utf-8"
        resp.raise_for_status()
        data = resp.json().get("data", [])

        prices = {}
        for item in data:
            fuel_id = item.get("id")
            price = (item.get("price") or {}).get("price")
            try:
                prices[int(fuel_id)] = float(price) if price is not None else None
            except (TypeError, ValueError):
                prices[int(fuel_id)] = None
        return prices

    def enrich_with_prices(self, stations: list) -> list:
        """Дозагружает цены для каждой станции (параллельно)."""
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = [
                pool.submit(self._fetch_station_prices, st.gpna_id)
                for st in stations
            ]
            for st, fut in zip(stations, futures):
                try:
                    st.fuel_prices = fut.result()
                except (requests.RequestException, ValueError, RuntimeError):
                    pass
        return stations


def fuel_label(fuel_id: int) -> str:
    return FUEL_NAMES.get(fuel_id, f"Топливо-{fuel_id}")