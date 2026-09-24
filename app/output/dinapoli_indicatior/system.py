"""Spięcie wszystkiego w system.

Przepływ jest dokładnie taki, jak w dokumencie źródłowym:

    1. kontekst z wyższych interwałów (M -> W) decyduje, w którą stronę wolno grać
    2. poziomy Fibo ze wszystkich interwałów lądują w jednym worku
    3. silnik Zgodności zamienia je w strefy
    4. setup na interwale dziennym daje moment wejścia
    5. SL idzie pod strefę, zasięgi to COP/OP/XOP
    6. filtr wykupienia blokuje wejście w rozgrzany rynek
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from .config import Config, DEFAULT
from .confluence import Zone, find_zones, nearest_resistance, nearest_support
from .indicators import compute_all
from .levels import Level, all_levels, projection_targets
from .setups import Setup, scan_bar
from .swings import Swing, detect_swings
from .trend import DOWN, SIDE, UP, resample, trend_alignment, trend_state


@dataclass
class Signal:
    date: pd.Timestamp
    idx: int
    side: str
    setup: str
    entry: float
    sl: float
    targets: Dict[str, float]
    rr: float
    trend: Dict[str, str]
    context: str
    zone: Optional[Zone] = None
    note: str = ""

    @property
    def risk(self) -> float:
        return abs(self.entry - self.sl)

    def describe(self) -> str:
        t = " / ".join(f"{k} {v:.2f}" for k, v in self.targets.items())
        return (f"{self.date:%Y-%m-%d}  {self.side.upper():5s} {self.setup:9s} "
                f"wejscie {self.entry:.2f}  SL {self.sl:.2f}  RR {self.rr:.2f}\n"
                f"    zasiegi: {t}\n"
                f"    trend D/W/M: {self.trend.get('D')}/{self.trend.get('W')}/"
                f"{self.trend.get('M')}  ({self.context})\n"
                f"    {self.note}")


@dataclass
class Snapshot:
    """Pełny stan rynku na jednej świecy."""
    idx: int
    date: pd.Timestamp
    price: float
    trend: Dict[str, str]
    context: str
    zones: List[Zone]
    levels: List[Level]
    support: Optional[Zone]
    resistance: Optional[Zone]
    setups: List[Setup]
    swings: List[Swing] = field(default_factory=list)
    overbought: bool = False
    oversold: bool = False
    macd_pred: float = float("nan")

    def report(self) -> str:
        lines = [
            f"=== {self.date:%Y-%m-%d}  cena {self.price:.2f} ===",
            f"Trend  D:{self.trend['D']}  W:{self.trend['W']}  M:{self.trend['M']}"
            f"   -> {self.context}",
            "MacdPred " + ("brak (poza zasiegiem)" if np.isnan(self.macd_pred)
                           else f"{self.macd_pred:.2f}")
            + ("  [WYKUPIENIE]" if self.overbought else "")
            + ("  [WYPRZEDANIE]" if self.oversold else ""),
        ]
        if self.resistance:
            lines.append(f"Opor   {self.resistance}")
        if self.support:
            lines.append(f"Wsparcie {self.support}")
        if self.setups:
            lines.append("Setupy: " + ", ".join(str(s) for s in self.setups))
        return "\n".join(lines)


class Analyzer:
    """Główny obiekt. Karmisz go OHLCV na interwale dziennym, resztę robi sam."""

    def __init__(self, df: pd.DataFrame, cfg: Config = DEFAULT,
                 symbol: str = "?"):
        req = {"open", "high", "low", "close"}
        if not req.issubset(df.columns):
            raise ValueError(f"DataFrame musi zawierac {req}, ma {set(df.columns)}")
        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError("Indeks musi byc DatetimeIndex")

        self.cfg = cfg
        self.symbol = symbol
        self.df = compute_all(df.sort_index(), cfg.indicator)
        self._htf_cache: Dict[str, pd.DataFrame] = {}

    # -- interwały wyższe ---------------------------------------------------

    def _htf(self, rule: str) -> pd.DataFrame:
        if rule not in self._htf_cache:
            self._htf_cache[rule] = resample(self.df, rule)
        return self._htf_cache[rule]

    def _htf_slice(self, rule: str, date: pd.Timestamp) -> pd.DataFrame:
        """Świece wyższego interwału domknięte najpóźniej w dniu `date`.

        Odcięcie po dacie zamknięcia gwarantuje, że w backteście nie
        korzystamy ze świecy tygodniowej, która jeszcze trwa.
        """
        h = self._htf(rule)
        return h[h.index <= date]

    # -- rdzeń --------------------------------------------------------------

    def snapshot(self, i: Optional[int] = None) -> Snapshot:
        """Stan rynku na świecy `i` (domyślnie ostatniej)."""
        if i is None:
            i = len(self.df) - 1
        row = self.df.iloc[i]
        date = self.df.index[i]
        price = float(row["close"])
        atr_v = float(row["atr"]) if not pd.isna(row["atr"]) else price * 0.01

        d_hist = self.df.iloc[:i + 1]
        sw_d = detect_swings(d_hist, self.cfg.swing)

        levels: List[Level] = all_levels(sw_d, self.cfg.level, "D")
        trends = {"D": trend_state(sw_d)}

        for rule, tag in (("W", "W"), ("ME", "M")):
            h = self._htf_slice(rule, date)
            if len(h) < 10:
                trends[tag] = SIDE
                continue
            sw_h = detect_swings(h, self.cfg.swing)
            trends[tag] = trend_state(sw_h)
            for lv in all_levels(sw_h, self.cfg.level, tag):
                lv.swing_id += 10_000 * (1 if tag == "W" else 2)
                levels.append(lv)

        zones = find_zones(levels, price, atr_v, self.cfg.confluence)
        sup = nearest_support(zones, price)
        res = nearest_resistance(zones, price)
        setups = scan_bar(self.df, i, sw_d, zones, self.cfg.setup)

        return Snapshot(
            idx=i, date=date, price=price, trend=trends,
            context=trend_alignment(trends), zones=zones, levels=levels,
            support=sup, resistance=res, setups=setups, swings=sw_d,
            overbought=bool(row.get("overbought", False)),
            oversold=bool(row.get("oversold", False)),
            macd_pred=float(row.get("macd_pred", np.nan)),
        )

    # -- sygnały ------------------------------------------------------------

    def _build_signal(self, snap: Snapshot, setup: Setup) -> Optional[Signal]:
        cfg = self.cfg
        row = self.df.iloc[snap.idx]
        atr_v = float(row["atr"]) if not pd.isna(row["atr"]) else snap.price * 0.01
        buf = atr_v * cfg.risk.sl_buffer_atr

        # filtr kontekstu wyższego interwału
        if cfg.setup.require_higher_tf:
            if setup.side == "long" and snap.trend["W"] == DOWN:
                return None
            if setup.side == "short" and snap.trend["W"] == UP:
                return None
        if cfg.setup.require_full_context:
            want = UP if setup.side == "long" else DOWN
            if snap.trend["W"] != want:
                return None

        # filtr wykupienia / wyprzedania
        if cfg.setup.block_when_overbought:
            if setup.side == "long" and snap.overbought:
                return None
            if setup.side == "short" and snap.oversold:
                return None

        entry = setup.entry
        if setup.side == "long":
            base = snap.support.low if snap.support else float(row["low"])
            sl = base - buf
            pool = [lv for lv in snap.levels
                    if lv.kind == "expansion" and lv.price > entry]
            pool.sort(key=lambda lv: lv.price)
        else:
            base = snap.resistance.high if snap.resistance else float(row["high"])
            sl = base + buf
            pool = [lv for lv in snap.levels
                    if lv.kind == "expansion" and lv.price < entry]
            pool.sort(key=lambda lv: -lv.price)

        # SL postawiony tuż pod ceną wejścia daje na papierze fantastyczne RR
        # i jest wyjmowany pierwszym szumem. Wymuszamy minimalny dystans.
        min_risk = atr_v * cfg.risk.min_risk_atr
        if abs(entry - sl) < min_risk:
            sl = entry - min_risk if setup.side == "long" else entry + min_risk
        risk = abs(entry - sl)
        if risk <= 0:
            return None

        targets = projection_targets(snap.swings, setup.side, entry, cfg.level)
        if not targets:
            for name in ("COP", "OP", "XOP"):
                hit = next((lv for lv in pool if lv.name == name), None)
                if hit:
                    targets[name] = round(hit.price, 4)
        if not targets:
            res = snap.resistance if setup.side == "long" else snap.support
            if res is None:
                return None
            targets["strefa"] = round(res.mid, 4)

        # RR liczymy do pierwszego celu, ale przycinamy go najbliższą strefą
        # po drodze. Bez tego XOP oddalony o 20% zawsze dawałby piękne RR,
        # które nigdy się nie zrealizuje - cena zatrzyma się na Zgodności.
        first = list(targets.values())[0]
        blocker = snap.resistance if setup.side == "long" else snap.support
        if blocker is not None:
            edge = blocker.low if setup.side == "long" else blocker.high
            if setup.side == "long" and entry < edge < first:
                first = edge
            elif setup.side == "short" and first < edge < entry:
                first = edge
        rr = abs(first - entry) / risk
        if rr < cfg.risk.min_rr:
            return None

        zone = snap.support if setup.side == "long" else snap.resistance
        return Signal(date=snap.date, idx=snap.idx, side=setup.side,
                      setup=setup.name, entry=round(entry, 4), sl=round(sl, 4),
                      targets=targets, rr=round(rr, 2), trend=snap.trend,
                      context=snap.context, zone=zone, note=setup.note)

    def signal(self, i: Optional[int] = None) -> Optional[Signal]:
        snap = self.snapshot(i)
        for s in snap.setups:
            sig = self._build_signal(snap, s)
            if sig:
                return sig
        return None

    def scan(self, start: int = 250, step: int = 1,
             verbose: bool = False) -> List[Signal]:
        """Przejście po historii. Zwraca listę sygnałów."""
        out: List[Signal] = []
        for i in range(start, len(self.df), step):
            sig = self.signal(i)
            if sig:
                out.append(sig)
                if verbose:
                    print(sig.describe(), "\n")
        return out
