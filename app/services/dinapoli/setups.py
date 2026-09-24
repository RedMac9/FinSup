"""Setupy.

Cztery formacje, które w dokumencie padają najczęściej. Każda funkcja
patrzy tylko na dane do świecy `i` włącznie - zero zaglądania w przyszłość,
więc te same funkcje działają w backteście i na żywo.
"""

from dataclasses import dataclass
from typing import List, Optional

import numpy as np
import pandas as pd

from .config import SetupConfig
from .confluence import Zone, zone_at
from .swings import Swing


@dataclass
class Setup:
    idx: int
    name: str          # "B&B", "DRePo", "W&R", "Zgodnosc"
    side: str          # "long" | "short"
    entry: float
    note: str = ""

    def __repr__(self):
        return f"Setup({self.name} {self.side} @{self.entry:.2f} bar={self.idx})"


# --------------------------------------------------------------------------

def bread_and_butter(df: pd.DataFrame, i: int, cfg: SetupConfig) -> Optional[Setup]:
    """B&B - pierwszy powrót do DMA 3x3 po dłuższej nieobecności.

    Warunki: cena zrobiła nowy ekstrem, przez >= 8 świec nie dotykała
    DMA 3x3, a teraz wraca do niej po raz pierwszy. Wejście na średniej.
    """
    need = cfg.bb_min_bars_away + 5
    if i < need:
        return None

    d = df.iloc[:i + 1]
    dma = d["dma_fast"]
    if pd.isna(dma.iloc[-1]):
        return None

    lo, hi, cl = d["low"], d["high"], d["close"]
    win = slice(-(cfg.bb_min_bars_away + 1), -1)

    # wariant long: świece trzymały się nad DMA, teraz dołek jej dotyka
    above = (lo.iloc[win] > dma.iloc[win]).all()
    new_high = hi.iloc[-1 - cfg.bb_min_bars_away:].max() == hi.iloc[-need:].max()
    touch_long = lo.iloc[-1] <= dma.iloc[-1] <= hi.iloc[-1]
    if above and new_high and touch_long:
        return Setup(i, "B&B", "long", float(dma.iloc[-1]),
                     f"pierwszy powrot do DMA3x3 po {cfg.bb_min_bars_away}+ swiecach")

    below = (hi.iloc[win] < dma.iloc[win]).all()
    new_low = lo.iloc[-1 - cfg.bb_min_bars_away:].min() == lo.iloc[-need:].min()
    touch_short = lo.iloc[-1] <= dma.iloc[-1] <= hi.iloc[-1]
    if below and new_low and touch_short:
        return Setup(i, "B&B", "short", float(dma.iloc[-1]),
                     f"pierwszy powrot do DMA3x3 po {cfg.bb_min_bars_away}+ swiecach")
    return None


def double_repo(df: pd.DataFrame, i: int, cfg: SetupConfig) -> Optional[Setup]:
    """DRePo - podwójna penetracja DMA 3x3.

    Cena przebija średnią, wraca, przebija znowu. Druga penetracja bez
    kontynuacji to wyczerpanie ruchu - sygnał w stronę przeciwną do
    penetracji, czyli powrót do dominującego trendu.
    """
    if i < cfg.drepo_max_gap + 4:
        return None

    d = df.iloc[:i + 1]
    dma, cl = d["dma_fast"], d["close"]
    if pd.isna(dma.iloc[-1]):
        return None

    rel = np.sign((cl - dma).iloc[-(cfg.drepo_max_gap + 4):].to_numpy())
    if len(rel) < 5 or np.isnan(rel).any():
        return None

    # szukamy sekwencji znaków: + - + -  (dwie penetracje w dół)
    flips = [k for k in range(1, len(rel)) if rel[k] != 0 and rel[k] != rel[k - 1]]
    if len(flips) < 3:
        return None

    last3 = flips[-3:]
    if rel[-1] > 0 and rel[last3[0]] < 0 and rel[last3[1]] > 0 and rel[last3[2]] > 0:
        pass  # obsłużone niżej ogólnie

    # sygnał long: dwie penetracje w dół zakończone powrotem nad średnią
    down_pens = sum(1 for k in flips[-3:] if rel[k] < 0)
    if rel[-1] > 0 and down_pens >= 2:
        return Setup(i, "DRePo", "long", float(cl.iloc[-1]),
                     "druga penetracja DMA3x3 w dol bez kontynuacji")

    up_pens = sum(1 for k in flips[-3:] if rel[k] > 0)
    if rel[-1] < 0 and up_pens >= 2:
        return Setup(i, "DRePo", "short", float(cl.iloc[-1]),
                     "druga penetracja DMA3x3 w gore bez kontynuacji")
    return None


def wash_and_rinse(df: pd.DataFrame, i: int, swings: List[Swing],
                   cfg: SetupConfig) -> Optional[Setup]:
    """W&R - wybicie ekstremum i natychmiastowy powrót (polowanie na stopy).

    Cena przebija poprzedni dołek/szczyt, ale w ciągu najbliższych kilku
    świec zamyka się z powrotem po właściwej stronie. Klasyczna pułapka.
    """
    if i < 5 or len(swings) < 3:
        return None

    d = df.iloc[:i + 1]
    prior = [s for s in swings if s.idx < i - 1]
    if len(prior) < 2:
        return None

    lows = [s for s in prior if s.kind == "L"]
    highs = [s for s in prior if s.kind == "H"]
    look = cfg.wr_max_bars_back

    if lows:
        ref = lows[-1].price
        broke = (d["low"].iloc[-look:] < ref).any()
        back = d["close"].iloc[-1] > ref
        if broke and back and d["low"].iloc[-look:].min() < ref:
            return Setup(i, "W&R", "long", float(d["close"].iloc[-1]),
                         f"wybicie dolka {ref:.2f} i powrot nad niego")

    if highs:
        ref = highs[-1].price
        broke = (d["high"].iloc[-look:] > ref).any()
        back = d["close"].iloc[-1] < ref
        if broke and back:
            return Setup(i, "W&R", "short", float(d["close"].iloc[-1]),
                         f"wybicie szczytu {ref:.2f} i powrot pod niego")
    return None


def confluence_bounce(df: pd.DataFrame, i: int, zones: List[Zone],
                      cfg: SetupConfig) -> Optional[Setup]:
    """Odbicie od strefy Zgodności - podstawowy setup z dokumentu.

    Cena schodzi w strefę wsparcia zbudowaną z poziomów z różnych fal,
    a świeca zamyka się nad nią. To jest to "test wsparcia na Zgodności,
    tu może być próba odbicia".
    """
    if i < 2 or not zones:
        return None

    row = df.iloc[i]
    prev = df.iloc[i - 1]
    atr_v = row.get("atr", 0.0)
    pad = atr_v * 0.1

    z = zone_at(zones, float(row["low"]), pad)
    if z is not None and z.direction == "support":
        if row["close"] > z.high and row["close"] > row["open"]:
            return Setup(i, "Zgodnosc", "long", float(row["close"]),
                         f"odbicie od {z.grade} {z.low:.2f}-{z.high:.2f} "
                         f"({z.names}, sila {z.strength})")

    z = zone_at(zones, float(row["high"]), pad)
    if z is not None and z.direction == "resistance":
        if row["close"] < z.low and row["close"] < row["open"]:
            return Setup(i, "Zgodnosc", "short", float(row["close"]),
                         f"odpadniecie od {z.grade} {z.low:.2f}-{z.high:.2f} "
                         f"({z.names}, sila {z.strength})")
    return None


def scan_bar(df: pd.DataFrame, i: int, swings: List[Swing], zones: List[Zone],
             cfg: SetupConfig) -> List[Setup]:
    """Wszystkie setupy na danej świecy. Kolejność = priorytet."""
    found = []
    for fn in (lambda: confluence_bounce(df, i, zones, cfg),
               lambda: bread_and_butter(df, i, cfg),
               lambda: double_repo(df, i, cfg),
               lambda: wash_and_rinse(df, i, swings, cfg)):
        s = fn()
        if s is not None:
            found.append(s)
    return found
