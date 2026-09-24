"""Silnik Zgodności i Zgęszczenia.

Serce systemu. Pojedynczy poziom Fibo znaczy niewiele. Wartość ma miejsce,
w którym poziomy z *różnych* fal - a najlepiej z różnych interwałów -
wypadają w tej samej cenie. Tam autorka dokumentu stawia zlecenia i SL,
i to te strefy są na wykresach zaznaczone kolorowymi prostokątami.

Definicje przyjęte w kodzie:
    Zgodność   (confluence) - >= 2 poziomy z różnych fal w tolerancji
    Zgęszczenie (congestion) - >= min_congestion poziomów, strefa zamiast linii
    Kumulacja ekspansji      - strefa złożona wyłącznie z zasięgów COP/OP/XOP
"""

from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

from .config import ConfluenceConfig
from .levels import Level


@dataclass
class Zone:
    """Strefa Zgodności/Zgęszczenia."""
    low: float
    high: float
    levels: List[Level] = field(default_factory=list)
    price_ref: float = 0.0   # cena, względem której strefa była oceniana
    min_congestion: int = 3  # ConfluenceConfig.min_congestion (ustawia find_zones)

    @property
    def mid(self) -> float:
        return (self.low + self.high) / 2

    @property
    def width(self) -> float:
        return self.high - self.low

    @property
    def count(self) -> int:
        return len(self.levels)

    @property
    def n_swings(self) -> int:
        return len({lv.swing_id for lv in self.levels})

    @property
    def n_timeframes(self) -> int:
        return len({lv.timeframe for lv in self.levels})

    @property
    def is_expansion_cluster(self) -> bool:
        """Strefa złożona WYŁĄCZNIE z zasięgów (COP/OP/XOP) - to, co autorka
        nazywa "kumulacją ekspansji" i traktuje osobno od Zgodności ze zniesień."""
        return bool(self.levels) and all(lv.kind == "expansion" for lv in self.levels)

    @property
    def grade(self) -> str:
        if self.is_expansion_cluster:
            return "Kumulacja ekspansji"
        return "Zgeszczenie" if self.count >= self.min_congestion else "Zgodnosc"

    @property
    def pl_grade(self) -> str:
        """grade z polskimi znakami - do etykiet na wykresie."""
        return {"Zgeszczenie": "Zgęszczenie", "Zgodnosc": "Zgodność"}.get(self.grade, self.grade)

    @property
    def pl_names(self) -> str:
        """Składowe w nazewnictwie autorki, np. 'PDw+W5d'."""
        return "+".join(sorted({lv.pl_short for lv in self.levels}))

    @property
    def origin_date(self):
        """Data powstania strefy = najpóźniej powstały poziom składowy
        (dopiero wtedy wszystkie jej poziomy istnieją jednocześnie)."""
        dates = [lv.origin_date for lv in self.levels if lv.origin_date is not None]
        return max(dates) if dates else None

    @property
    def direction(self) -> str:
        """Strefa pod ceną to wsparcie, nad ceną to opór - niezależnie od
        tego, z jakich poziomów powstała. Gdy brak ceny referencyjnej,
        wracamy do pochodzenia poziomów."""
        if self.price_ref:
            return "support" if self.mid <= self.price_ref else "resistance"
        sup = sum(1 for lv in self.levels if lv.direction == "support")
        return "support" if sup * 2 >= self.count else "resistance"

    @property
    def strength(self) -> float:
        """Siła strefy w skali ~0-10.

        Premiujemy liczbę poziomów, różnorodność fal, obecność wyższych
        interwałów (poziom tygodniowy waży więcej niż dzienny) oraz
        wielkość fal, z których poziomy pochodzą.
        """
        tf_w = {"D": 1.0, "W": 1.6, "M": 2.2}
        raw = sum(tf_w.get(lv.timeframe, 1.0) for lv in self.levels)
        raw *= 1 + 0.15 * (self.n_swings - 1)
        raw *= 1 + 0.20 * (self.n_timeframes - 1)
        # miękkie wysycenie zamiast twardego obcięcia - inaczej każda
        # nieco gęstsza strefa dostawała 10.0 i skala przestawała rozróżniać
        return round(10.0 * (1 - np.exp(-raw / 7.0)), 2)

    @property
    def names(self) -> str:
        return "+".join(sorted({lv.label for lv in self.levels}))

    def __repr__(self):
        return (f"Zone[{self.grade} {self.direction}] {self.low:.2f}-{self.high:.2f} "
                f"n={self.count} sila={self.strength} ({self.names})")


def _tolerance(price: float, atr_value: float, cfg: ConfluenceConfig) -> float:
    if cfg.tolerance_mode == "pct":
        return price * cfg.tolerance_pct
    return atr_value * cfg.tolerance_atr


def find_zones(levels: List[Level], price: float, atr_value: float,
               cfg: ConfluenceConfig) -> List[Zone]:
    """Klastrowanie jednowymiarowe metodą łańcuchową.

    Sortujemy poziomy po cenie i łączymy sąsiadów, dopóki odstęp mieści się
    w tolerancji. Proste, deterministyczne i odporne - w przeciwieństwie do
    k-means nie trzeba z góry wiedzieć, ile stref powstanie.
    """
    if not levels:
        return []

    band = price * cfg.lookahead_pct
    pool = [lv for lv in levels if abs(lv.price - price) <= band]
    if not pool:
        return []

    pool.sort(key=lambda x: x.price)
    tol = _tolerance(price, atr_value, cfg)
    width = 2 * tol

    # Zachłanne okno o STAŁEJ szerokości. Wcześniejsza wersja łączyła
    # sąsiadów łańcuchowo, przez co gęsty obszar zlewał się w jedną strefę
    # szeroką na kilkanaście procent - bezużyteczną do stawiania SL.
    # Tutaj żadna strefa nie przekroczy 2*tolerancja.
    remaining = list(pool)
    clusters: List[List[Level]] = []
    while remaining:
        prices = [lv.price for lv in remaining]
        best_i, best_cnt = 0, 0
        for i, p0 in enumerate(prices):
            cnt = sum(1 for p in prices if p0 <= p <= p0 + width)
            if cnt > best_cnt:
                best_i, best_cnt = i, cnt
        lo = prices[best_i]
        chosen = [lv for lv in remaining if lo <= lv.price <= lo + width]
        clusters.append(chosen)
        remaining = [lv for lv in remaining if not (lo <= lv.price <= lo + width)]

    zones: List[Zone] = []
    for cl in clusters:
        if len(cl) < cfg.min_confluence:
            continue
        if cfg.require_distinct_swings and len({lv.swing_id for lv in cl}) < 2:
            continue
        zones.append(Zone(low=min(l.price for l in cl),
                          high=max(l.price for l in cl),
                          levels=cl, price_ref=price,
                          min_congestion=cfg.min_congestion))

    zones.sort(key=lambda z: z.mid)
    return zones


def nearest_support(zones: List[Zone], price: float,
                    min_strength: float = 0.0) -> Optional[Zone]:
    cands = [z for z in zones if z.high < price and z.strength >= min_strength]
    return max(cands, key=lambda z: z.high) if cands else None


def nearest_resistance(zones: List[Zone], price: float,
                       min_strength: float = 0.0) -> Optional[Zone]:
    cands = [z for z in zones if z.low > price and z.strength >= min_strength]
    return min(cands, key=lambda z: z.low) if cands else None


def zone_at(zones: List[Zone], price: float, pad: float = 0.0) -> Optional[Zone]:
    """Czy cena jest aktualnie wewnątrz którejś strefy."""
    hits = [z for z in zones if z.low - pad <= price <= z.high + pad]
    return max(hits, key=lambda z: z.strength) if hits else None
