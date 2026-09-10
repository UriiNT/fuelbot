from dataclasses import dataclass, field
from typing import Optional

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://auto.lukoil.ru"
SEARCH_API = BASE_URL + "/api/cartography/GetSearchObjects"
OBJECTS_API = BASE_URL + "/api/cartography/GetObjects"

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": BASE_URL + "/ru/ProductsAndServices/PetrolStations",
}


@dataclass
class LukoilStation:
    station_id: int
    number: str
    name: str
    address: str
    city: str
    latitude: float
    longitude: float
    status: int
    fuels: list = field(default_factory=list)  # [(name, price_float|None)]


class LukoilClient:
    def __init__(self, timeout: int = 30):
        self.session = requests.Session()
        self.session.verify = False
        self.session.headers.update(DEFAULT_HEADERS)
        self.timeout = timeout

    def _search_stations(self) -> list:
        try:
            resp = self.session.get(
                SEARCH_API,
                params={"form": "gasStation"},
                timeout=self.timeout,
            )
            resp.encoding = "utf-8"
            resp.raise_for_status()
            data = resp.json()
        except (requests.RequestException, ValueError) as exc:
            raise RuntimeError(f"Лукойл: ошибка поиска АЗС: {exc}") from exc

        return data.get("GasStations", [])

    def _get_details(self, ids: list) -> list:
        """Получает детали станций. ids — список gasStation{id}."""
        if not ids:
            return []
        try:
            resp = self.session.get(
                OBJECTS_API,
                params=[("ids", i) for i in ids] + [("LanguageCode", "ru")],
                timeout=self.timeout,
            )
            resp.encoding = "utf-8"
            resp.raise_for_status()
            data = resp.json()
        except (requests.RequestException, ValueError) as exc:
            raise RuntimeError(f"Лукойл: ошибка запроса деталей АЗС: {exc}") from exc

        return data

    def get_stations_by_city(self, city_fragment: str = "тагил") -> list:
        needle = city_fragment.lower()
        raw = [st for st in self._search_stations()
               if needle in (st.get("City") or "").lower()]

        stations = []
        # Запрашиваем детали пакетами (защита от слишком длинного URL)
        detail_map = {}
        ids = [f"gasStation{st['GasStationId']}" for st in raw]
        for i in range(0, len(ids), 20):
            batch = ids[i:i + 20]
            for detail in self._get_details(batch):
                if not detail:
                    continue
                gs = detail.get("GasStation") or {}
                gs_id = gs.get("GasStationId")
                if gs_id is not None:
                    detail_map[gs_id] = detail

        for st in raw:
            gid = st.get("GasStationId")
            detail = detail_map.get(gid) or {}
            gs = detail.get("GasStation") or {}
            number = gs.get("StationNumber") or st.get("StationNumber") or ""
            street = st.get("Street")
            if not street:
                street = gs.get("Address") or ""
            fuels = []
            for fuel in detail.get("Fuels", []) or []:
                price = fuel.get("Price")
                try:
                    price = float(price) if price is not None else None
                except (TypeError, ValueError):
                    price = None
                fuels.append((fuel.get("Name") or "", price))

            stations.append(
                LukoilStation(
                    station_id=gid,
                    number=number,
                    name=st.get("DisplayName") or "",
                    address=street,
                    city=st.get("City") or "",
                    latitude=float(st.get("Latitude") or 0),
                    longitude=float(st.get("Longitude") or 0),
                    status=st.get("GasStationStatus", 0),
                    fuels=fuels,
                )
            )
        return stations