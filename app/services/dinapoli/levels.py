"""Węzły Fibonacciego (Fibnodes) i zasięgi (objective points).

Nazewnictwo trzyma się oryginału, z polskimi odpowiednikami z dokumentu:

    F3  = zniesienie 38.2%   ("W3")
    F5  = zniesienie 61.8%   ("W5")
    COP = ekspansja 0.618    ("BPD" - bliższy punkt docelowy)
    OP  = ekspansja 1.000    ("PD")
    XOP = ekspansja 1.618    ("DPD" - dalszy punkt docelowy)

Zniesienia 50% świadomie nie ma - DiNapoli jej nie używa i na wykresach
z dokumentu też jej nie widać.
"""

from dataclasses import dataclass
from typing import List, Optional

import pandas as pd

from .config import LevelConfig
from .swings import Leg, Swing, abc_structures, build_legs

# Nazwy z dokumentu źródłowego: skrót + procent, jak na wykresach autorki.
PL_NAMES = {
    "F3": ("W3", "38.2%"),
    "F5": ("W5", "61.8%"),
    "COP": ("BPD", "61.8%"),
    "OP": ("PD", "100%"),
    "XOP": ("DPD", "161.8%"),
}


@dataclass
class Level:
    """Pojedynczy poziom Fibo z metryką jego 'wagi'."""
    price: float
    name: str            # F3, F5, COP, OP, XOP
    kind: str            # "retracement" | "expansion"
    direction: str       # "support" | "resistance"
    swing_id: int        # z której fali pochodzi - klucz dla Zgodności
    timeframe: str = "D"
    leg_size: float = 0.0
    leg_bars: int = 0
    # Świeca (w DataFrame SWOJEGO interwału), od której poziom jest znany:
    # koniec fali dla zniesień, punkt C dla zasięgów. Data uzupełniana przez
    # Analyzer.snapshot() - pozwala rysować poziom od miejsca powstania,
    # a nie od początku historii.
    origin_idx: int = -1
    origin_date: Optional[pd.Timestamp] = None

    @property
    def label(self) -> str:
        return f"{self.name}{self.timeframe}"

    @property
    def pl_short(self) -> str:
        """'W5' / 'PD' + interwał małą literą, np. 'PDm' jak na wykresach."""
        short, _ = PL_NAMES.get(self.name, (self.name, ""))
        return f"{short}{self.timeframe.lower()}"

    @property
    def pl_label(self) -> str:
        """Pełna etykieta w nazewnictwie autorki, np. 'W5d 61.8% 331.69'."""
        _, pct = PL_NAMES.get(self.name, (self.name, ""))
        return f"{self.pl_short} {pct} {self.price:.2f}".replace("  ", " ")

    def __repr__(self):
        return f"Level({self.label} {self.price:.2f} {self.direction})"


def retracement_levels(legs: List[Leg], cfg: LevelConfig, timeframe: str = "D",
                       offset: int = 0) -> List[Level]:
    """Zniesienia z każdej fali.

    Fala w górę daje wsparcia (cena cofa się w dół), fala w dół daje opory.
    """
    out: List[Level] = []
    for i, leg in enumerate(legs):
        if leg.size <= 0:
            continue
        for ratio, name in zip(cfg.retracements, cfg.retracement_names):
            if leg.up:
                price = leg.end.price - ratio * leg.size
                direction = "support"
            else:
                price = leg.end.price + ratio * leg.size
                direction = "resistance"
            out.append(Level(price, name, "retracement", direction,
                             swing_id=offset + i, timeframe=timeframe,
                             leg_size=leg.size, leg_bars=leg.bars,
                             origin_idx=leg.end.idx))
    return out


def expansion_levels(swings: List[Swing], cfg: LevelConfig, timeframe: str = "D",
                     offset: int = 1000) -> List[Level]:
    """Zasięgi COP / OP / XOP z każdej struktury A-B-C.

    Ruch A->B rzutowany z punktu C. To są te '61.8% / 100% / 161.8%'
    rozsiane po wykresach z dokumentu - autorka nazywa ich skupisko
    "kumulacją ekspansji".
    """
    out: List[Level] = []
    for i, (a, b, c, direction) in enumerate(abc_structures(swings)):
        span = abs(b.price - a.price)
        if span <= 0:
            continue
        for ratio, name in zip(cfg.expansions, cfg.expansion_names):
            if direction == "up":
                price = c.price + ratio * span
                d = "resistance"
            else:
                price = c.price - ratio * span
                d = "support"
            out.append(Level(price, name, "expansion", d,
                             swing_id=offset + i, timeframe=timeframe,
                             leg_size=span, leg_bars=b.idx - a.idx,
                             origin_idx=c.idx))
    return out


def projection_targets(swings: List[Swing], side: str, entry: float,
                       cfg: LevelConfig) -> dict:
    """Komplet COP/OP/XOP z JEDNEJ, najświeższej struktury A-B-C.

    Kluczowe, żeby brać wszystkie trzy zasięgi z tej samej struktury -
    inaczej COP z jednej fali i OP z innej wychodzą w przypadkowej
    kolejności i przestają być sensowną drabinką celów.
    """
    want = "up" if side == "long" else "down"
    for a, b, c, direction in reversed(abc_structures(swings)):
        if direction != want:
            continue
        span = abs(b.price - a.price)
        if span <= 0:
            continue
        out = {}
        for ratio, name in zip(cfg.expansions, cfg.expansion_names):
            p = c.price + ratio * span if want == "up" else c.price - ratio * span
            out[name] = round(p, 4)
        beyond = {k: v for k, v in out.items()
                  if (v > entry if want == "up" else v < entry)}
        if beyond:
            return beyond
    return {}


def all_levels(swings: List[Swing], cfg: LevelConfig,
               timeframe: str = "D") -> List[Level]:
    legs = build_legs(swings)
    lv = retracement_levels(legs, cfg, timeframe, offset=0)
    lv += expansion_levels(swings, cfg, timeframe, offset=1000)
    return lv
