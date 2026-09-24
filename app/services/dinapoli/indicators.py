"""Wskaźniki bazowe + Predictory.

MACD Predictor i Oscillator Predictor to pomysł DiNapoliego: zamiast pytać
"co robi wskaźnik", pytamy "przy jakiej cenie wskaźnik da sygnał na następnej
świecy". Odpowiedź jest linią na wykresie cenowym, więc działa jak wsparcie
albo opór.
"""

import numpy as np
import pandas as pd

from .config import IndicatorConfig


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    h, l, c = df["high"], df["low"], df["close"]
    prev = c.shift(1)
    tr = pd.concat([h - l, (h - prev).abs(), (l - prev).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def dma(series: pd.Series, period: int, displace: int) -> pd.Series:
    """Displaced Moving Average - SMA przesunięta w przyszłość o `displace` świec.

    DMA 3x3 to SMA(3) narysowana 3 świece do przodu. Przesunięcie w prawo
    oznacza, że ostatnie `displace` wartości to projekcja: są znane, zanim
    cena tam dojdzie. To dlatego DMA 3x3 działa jako poziom wejścia.
    """
    return series.rolling(period).mean().shift(displace)


def moving_averages(df: pd.DataFrame, cfg: IndicatorConfig) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    c = df["close"]
    out["dma_fast"] = dma(c, *cfg.dma_fast)
    out["dma_mid"] = dma(c, *cfg.dma_mid)
    out["dma_slow"] = dma(c, *cfg.dma_slow)
    for p in cfg.ma_periods:
        out[f"ma{p}"] = c.rolling(p).mean()
    return out


# --------------------------------------------------------------------------
# MACD Predictor
# --------------------------------------------------------------------------

def macd_predictor(close: pd.Series, fast: int = 12, slow: int = 26,
                   signal: int = 9) -> pd.Series:
    """Cena, przy której na następnej świecy MACD zrówna się z linią sygnału.

    Wyprowadzenie (a_x = 2/(x+1)):

        MACD' = (a_f - a_s)*P + (1-a_f)*EMAf + -(1-a_s)*EMAs
        Sig'  = a_g*MACD' + (1-a_g)*Sig
        MACD' - Sig' = (1-a_g) * (MACD' - Sig)

    Czyli przecięcie zachodzi dokładnie wtedy, gdy MACD' = Sig (dzisiejsza
    wartość sygnału). Podstawiamy i rozwiązujemy względem P:

        P = [ Sig - (1-a_f)*EMAf + (1-a_s)*EMAs ] / (a_f - a_s)

    Forma zamknięta, bez iteracji.
    """
    a_f, a_s = 2 / (fast + 1), 2 / (slow + 1)
    ema_f = close.ewm(span=fast, adjust=False).mean()
    ema_s = close.ewm(span=slow, adjust=False).mean()
    macd = ema_f - ema_s
    sig = macd.ewm(span=signal, adjust=False).mean()
    pred = (sig - (1 - a_f) * ema_f + (1 - a_s) * ema_s) / (a_f - a_s)

    # Predictor potrafi wystrzelić w kosmos, gdy MACD i sygnał są prawie
    # równoległe - mianownik jest wtedy nieistotny wobec licznika. Poziom
    # oddalony o 30 ATR nie jest wsparciem, więc go odcinamy.
    band = 3.0 * (close.rolling(20).std().bfill() + 1e-12)
    pred = pred.where((pred - close).abs() <= band)
    return pred.rename("macd_pred")


def macd_line(close: pd.Series, fast: int = 12, slow: int = 26,
              signal: int = 9) -> pd.DataFrame:
    ema_f = close.ewm(span=fast, adjust=False).mean()
    ema_s = close.ewm(span=slow, adjust=False).mean()
    macd = ema_f - ema_s
    sig = macd.ewm(span=signal, adjust=False).mean()
    return pd.DataFrame({"macd": macd, "signal": sig, "hist": macd - sig})


# --------------------------------------------------------------------------
# Oscillator Predictor
# --------------------------------------------------------------------------

def detrended_oscillator(close: pd.Series, period: int = 20) -> pd.Series:
    """Oscylator zdetrendowany: cena minus jej własna średnia.

    DiNapoli używa go zamiast RSI, bo nie ma sufitu ani podłogi - pokazuje,
    jak daleko cena odeszła od równowagi w jednostkach ceny, a nie w skali 0-100.
    """
    return (close - close.rolling(period).mean()).rename("detrended")


def oscillator_predictor(close: pd.Series, cfg: IndicatorConfig) -> pd.DataFrame:
    """Pasma cenowe wykupienia i wyprzedania na następną świecę.

    Bierzemy rozkład historyczny oscylatora zdetrendowanego, wycinamy z niego
    kwantyle, po czym przekładamy je z powrotem na cenę przez projekcję
    średniej. Wynik: dwie linie na wykresie cenowym mówiące "powyżej tego
    poziomu rynek będzie wykupiony".

    Uwaga: oryginalna formuła DiNapoliego jest zamknięta i komercyjna.
    To jest rekonstrukcja oparta na tej samej idei, nie kopia.
    """
    n = cfg.detrend_period
    do = detrended_oscillator(close, n)
    hi_q = do.rolling(cfg.osc_lookback, min_periods=n * 2).quantile(cfg.osc_quantile)
    lo_q = do.rolling(cfg.osc_lookback, min_periods=n * 2).quantile(1 - cfg.osc_quantile)

    # projekcja jutrzejszej SMA przy założeniu, że cena = szukany poziom P:
    #   SMA' = (suma_bez_najstarszej + P) / n
    #   DO'  = P - SMA' = P*(n-1)/n - suma_bez_najstarszej/n
    #   P    = (DO' + suma_bez_najstarszej/n) * n/(n-1)
    roll_sum = close.rolling(n).sum()
    base = (roll_sum - close.shift(n - 1)) / n

    k = n / (n - 1)
    overbought = (hi_q + base) * k
    oversold = (lo_q + base) * k

    return pd.DataFrame({
        "osc_overbought": overbought,
        "osc_oversold": oversold,
        "detrended": do,
    })


def is_overbought(close: pd.Series, osc: pd.DataFrame) -> pd.Series:
    return close >= osc["osc_overbought"]


def is_oversold(close: pd.Series, osc: pd.DataFrame) -> pd.Series:
    return close <= osc["osc_oversold"]


def compute_all(df: pd.DataFrame, cfg: IndicatorConfig) -> pd.DataFrame:
    """Jeden przebieg: wszystkie wskaźniki doklejone do OHLCV."""
    out = df.copy()
    out = out.join(moving_averages(df, cfg))
    out["atr"] = atr(df, 14)
    out = out.join(macd_line(df["close"], *cfg.macd))
    out = out.join(macd_predictor(df["close"], *cfg.macd))
    out = out.join(oscillator_predictor(df["close"], cfg))
    out["overbought"] = is_overbought(df["close"], out)
    out["oversold"] = is_oversold(df["close"], out)
    return out
