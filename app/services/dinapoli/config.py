"""Parametry systemu. Wszystko, co warto stroić, jest tutaj."""

from dataclasses import dataclass, field


@dataclass
class SwingConfig:
    """Detekcja punktów zwrotnych (reaction points)."""
    method: str = "atr"          # "atr" | "pct" | "fractal"
    atr_period: int = 14
    atr_mult: float = 2.0        # próg zygzaka w ATR
    pct_threshold: float = 0.03  # próg zygzaka w % (gdy method="pct")
    fractal_k: int = 2           # ile świec z każdej strony (gdy method="fractal")
    max_swings: int = 40         # ile ostatnich fal brać do liczenia poziomów


@dataclass
class LevelConfig:
    """Węzły Fibonacciego i zasięgi."""
    # DiNapoli świadomie pomija 50% - węzły to wyłącznie F3 i F5
    retracements: tuple = (0.382, 0.618)
    # COP / OP / XOP
    expansions: tuple = (0.618, 1.000, 1.618)
    expansion_names: tuple = ("COP", "OP", "XOP")
    retracement_names: tuple = ("F3", "F5")


@dataclass
class ConfluenceConfig:
    """Silnik Zgodności i Zgęszczenia."""
    tolerance_mode: str = "atr"   # "atr" | "pct"
    tolerance_atr: float = 0.25   # szerokość klastra w ATR
    tolerance_pct: float = 0.004  # szerokość klastra w % ceny
    min_confluence: int = 2       # >= tyle poziomów -> Zgodność
    min_congestion: int = 3       # >= tyle poziomów -> Zgęszczenie
    require_distinct_swings: bool = True   # poziomy muszą pochodzić z różnych fal
    lookahead_pct: float = 0.35   # ile % ceny nad/pod rynkiem raportować


@dataclass
class IndicatorConfig:
    dma_fast: tuple = (3, 3)      # DMA 3x3 - kręgosłup setupów
    dma_mid: tuple = (7, 5)
    dma_slow: tuple = (25, 5)
    ma_periods: tuple = (50, 100, 200)
    macd: tuple = (12, 26, 9)
    detrend_period: int = 20      # okres oscylatora zdetrendowanego
    osc_quantile: float = 0.90    # percentyl dla stref wykupienia/wyprzedania
    osc_lookback: int = 250


@dataclass
class TrendConfig:
    """Stan trendu w ujęciu Dowa, liczony z fal."""
    confirm_swings: int = 2       # ile par szczyt/dołek analizować


@dataclass
class SetupConfig:
    bb_min_bars_away: int = 8     # B&B: ile świec z dala od DMA 3x3
    drepo_max_gap: int = 8        # DRePo: max świec między penetracjami
    wr_max_bars_back: int = 3     # W&R: ile świec na powrót za wybity ekstrem
    require_higher_tf: bool = True   # blokuj wejścia przeciw trendowi W
    require_full_context: bool = False  # wymagaj ZGODNEGO trendu W, nie tylko nieprzeciwnego
    block_when_overbought: bool = True


@dataclass
class RiskConfig:
    sl_buffer_atr: float = 0.35   # bufor pod strefą wsparcia
    min_risk_atr: float = 0.5     # minimalny dystans wejście-SL
    min_rr: float = 1.5           # minimalny stosunek zysk/ryzyko do COP
    trail_to_dma: bool = True     # zacieśnianie SL do DMA 3x3 po dojściu do OP


@dataclass
class Config:
    swing: SwingConfig = field(default_factory=SwingConfig)
    level: LevelConfig = field(default_factory=LevelConfig)
    confluence: ConfluenceConfig = field(default_factory=ConfluenceConfig)
    indicator: IndicatorConfig = field(default_factory=IndicatorConfig)
    trend: TrendConfig = field(default_factory=TrendConfig)
    setup: SetupConfig = field(default_factory=SetupConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)


DEFAULT = Config()
