"""Stan trendu per interwał.

W dokumencie "trend wzrostowy dzienny / tygodniowy / miesięczny" bramkuje
każdą decyzję, ale nigdzie nie jest zdefiniowany. Przyjmujemy klasyczną
definicję Dowa liczoną z wykrytych fal, bo to jedyna, która daje ten sam
wynik na każdym interwale i nie wymaga dobierania parametrów:

    wzrostowy  - ostatni szczyt wyższy od poprzedniego I ostatni dołek wyższy
    spadkowy   - ostatni szczyt niższy I ostatni dołek niższy
    boczny     - wszystko inne (konsolidacja)

Podmiana tej definicji na inną (np. cena względem DMA 25x5) sprowadza się
do zamiany jednej funkcji.
"""

from typing import Dict, List

import pandas as pd

from .swings import Swing

UP, DOWN, SIDE = "wzrostowy", "spadkowy", "boczny"


def trend_state(swings: List[Swing]) -> str:
    highs = [s for s in swings if s.kind == "H"]
    lows = [s for s in swings if s.kind == "L"]
    if len(highs) < 2 or len(lows) < 2:
        return SIDE

    hh = highs[-1].price > highs[-2].price
    hl = lows[-1].price > lows[-2].price
    lh = highs[-1].price < highs[-2].price
    ll = lows[-1].price < lows[-2].price

    if hh and hl:
        return UP
    if lh and ll:
        return DOWN
    return SIDE


def trend_alignment(states: Dict[str, str]) -> str:
    """Podsumowanie zgodności interwałów - to jest 'kontekst' z dokumentu."""
    vals = list(states.values())
    if all(v == UP for v in vals):
        return "pelna zgodnosc wzrostowa"
    if all(v == DOWN for v in vals):
        return "pelna zgodnosc spadkowa"
    higher = [v for k, v in states.items() if k in ("W", "M")]
    if higher and all(v == UP for v in higher):
        return "kontekst wzrostowy"
    if higher and all(v == DOWN for v in higher):
        return "kontekst spadkowy"
    return "brak zgodnosci"


def resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Agregacja OHLCV na wyższy interwał.

    label/closed='right' - świeca tygodniowa jest datowana swoim ostatnim
    dniem, więc przy mapowaniu z powrotem na dzienny nie zaglądamy w przyszłość.
    """
    agg = {"open": "first", "high": "max", "low": "min",
           "close": "last", "volume": "sum"}
    cols = {k: v for k, v in agg.items() if k in df.columns}
    out = df.resample(rule, label="right", closed="right").agg(cols)
    return out.dropna(subset=["close"])
