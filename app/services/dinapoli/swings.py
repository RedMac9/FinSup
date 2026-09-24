"""Detekcja punktów zwrotnych.

To fundament całej reszty: bez sensownych fal poziomy Fibo są losowe.
Zygzak ATR-owy skaluje próg do zmienności instrumentu, więc ten sam
parametr działa i na KGH, i na EURPLN.
"""

from dataclasses import dataclass
from typing import List

import numpy as np
import pandas as pd

from .config import SwingConfig
from .indicators import atr


@dataclass
class Swing:
    """Pojedynczy punkt zwrotny."""
    idx: int          # pozycja w DataFrame
    price: float
    kind: str         # "H" albo "L"

    def __repr__(self):
        return f"Swing({self.kind}@{self.idx}={self.price:.2f})"


@dataclass
class Leg:
    """Fala: odcinek między dwoma sąsiednimi punktami zwrotnymi."""
    start: Swing
    end: Swing

    @property
    def up(self) -> bool:
        return self.end.price > self.start.price

    @property
    def size(self) -> float:
        return abs(self.end.price - self.start.price)

    @property
    def bars(self) -> int:
        return self.end.idx - self.start.idx

    def __repr__(self):
        d = "UP" if self.up else "DN"
        return f"Leg({d} {self.start.price:.2f}->{self.end.price:.2f})"


def _zigzag(df: pd.DataFrame, threshold: pd.Series) -> List[Swing]:
    """Zygzak ze zmiennym progiem. `threshold` to seria w jednostkach ceny."""
    high = df["high"].to_numpy()
    low = df["low"].to_numpy()
    thr = threshold.to_numpy()
    n = len(df)
    if n < 3:
        return []

    swings: List[Swing] = []
    # start: zakładamy kierunek na podstawie pierwszego wyraźnego ruchu
    ext_i, ext_p, direction = 0, high[0], None
    cand_i, cand_p = 0, low[0]

    for i in range(1, n):
        t = thr[i] if not np.isnan(thr[i]) else (high[i] - low[i])
        if t <= 0:
            continue

        if direction is None:
            if high[i] - low[cand_i] >= t:
                direction = "up"
                swings.append(Swing(cand_i, low[cand_i], "L"))
                ext_i, ext_p = i, high[i]
            elif high[ext_i] - low[i] >= t:
                direction = "down"
                swings.append(Swing(ext_i, high[ext_i], "H"))
                ext_i, ext_p = i, low[i]
            else:
                if high[i] > high[ext_i]:
                    ext_i, ext_p = i, high[i]
                if low[i] < low[cand_i]:
                    cand_i, cand_p = i, low[i]
            continue

        if direction == "up":
            if high[i] > ext_p:
                ext_i, ext_p = i, high[i]
            elif ext_p - low[i] >= t:
                swings.append(Swing(ext_i, ext_p, "H"))
                direction = "down"
                ext_i, ext_p = i, low[i]
        else:
            if low[i] < ext_p:
                ext_i, ext_p = i, low[i]
            elif high[i] - ext_p >= t:
                swings.append(Swing(ext_i, ext_p, "L"))
                direction = "up"
                ext_i, ext_p = i, high[i]

    # ostatni, jeszcze niepotwierdzony ekstrem - potrzebny do liczenia
    # zasięgów na żywo, ale oznaczony jako tentative przez pozycję na końcu
    if direction is not None:
        swings.append(Swing(ext_i, ext_p, "H" if direction == "up" else "L"))

    return swings


def _fractals(df: pd.DataFrame, k: int) -> List[Swing]:
    high, low = df["high"].to_numpy(), df["low"].to_numpy()
    n = len(df)
    raw = []
    for i in range(k, n - k):
        w_h, w_l = high[i - k:i + k + 1], low[i - k:i + k + 1]
        if high[i] == w_h.max() and (w_h.argmax() == k):
            raw.append(Swing(i, high[i], "H"))
        elif low[i] == w_l.min() and (w_l.argmin() == k):
            raw.append(Swing(i, low[i], "L"))
    # usuwamy sąsiadujące punkty tego samego typu, zostawiając skrajny
    cleaned: List[Swing] = []
    for s in raw:
        if cleaned and cleaned[-1].kind == s.kind:
            better = (s.price > cleaned[-1].price) if s.kind == "H" else (s.price < cleaned[-1].price)
            if better:
                cleaned[-1] = s
        else:
            cleaned.append(s)
    return cleaned


def detect_swings(df: pd.DataFrame, cfg: SwingConfig) -> List[Swing]:
    if cfg.method == "fractal":
        sw = _fractals(df, cfg.fractal_k)
    elif cfg.method == "pct":
        sw = _zigzag(df, df["close"] * cfg.pct_threshold)
    else:
        sw = _zigzag(df, atr(df, cfg.atr_period) * cfg.atr_mult)
    return sw[-cfg.max_swings:] if cfg.max_swings else sw


def build_legs(swings: List[Swing]) -> List[Leg]:
    return [Leg(a, b) for a, b in zip(swings, swings[1:])]


def abc_structures(swings: List[Swing]):
    """Trójki A-B-C do liczenia zasięgów.

    Dla trendu wzrostowego: A = dołek, B = szczyt, C = wyższy dołek.
    Zwraca tylko struktury geometrycznie poprawne (C nie wybija A).
    """
    out = []
    for a, b, c in zip(swings, swings[1:], swings[2:]):
        if a.kind == "L" and b.kind == "H" and c.kind == "L" and c.price > a.price:
            out.append((a, b, c, "up"))
        elif a.kind == "H" and b.kind == "L" and c.kind == "H" and c.price < a.price:
            out.append((a, b, c, "down"))
    return out
