# dinapoli — system Zgodności, zasięgów i setupów

Implementacja metodyki odtworzonej z cotygodniowego komentarza rynkowego
(*Strategia.docx*, 12.09.2026). Analiza wykresów wykazała, że to warsztat
Joe DiNapoliego: przesunięte średnie 3x3 / 25x5, wyłącznie zniesienia 38,2%
i 61,8%, zasięgi 0,618 / 1,0 / 1,618 oraz autorskie Predictory.

## Mapowanie terminologii

| Dokument | Oryginał | W kodzie |
|---|---|---|
| W3 | Fibnode F3 (38,2%) | `Level(name="F3")` |
| W5 | Fibnode F5 (61,8%) | `Level(name="F5")` |
| Zgodność | Confluence | `Zone`, `count >= 2` |
| Zgęszczenie | — | `Zone`, `count >= 3` |
| BPD | COP (0,618) | `Level(name="COP")` |
| PD | OP (1,000) | `Level(name="OP")` |
| DPD | XOP (1,618) | `Level(name="XOP")` |
| kumulacja ekspansji | skupisko zasięgów | `Zone` z poziomów `kind="expansion"` |
| B&B | Bread & Butter | `setups.bread_and_butter` |
| DRePo | Double RePenetration | `setups.double_repo` |
| W&R | Wash & Rinse | `setups.wash_and_rinse` |
| MacdPred | MACD Predictor | `indicators.macd_predictor` |
| Osc.Pred | Oscillator Predictor | `indicators.oscillator_predictor` |

Sufiks przy nazwie poziomu to interwał: `F5W` = zniesienie 61,8% z wykresu
tygodniowego, `COPM` = COP z miesięcznego.

## Instalacja

```bash
pip install numpy pandas matplotlib
```

Scipy nie jest potrzebne. Pakiet jest czystym Pythonem.

## Użycie

```python
import pandas as pd
from dinapoli import Analyzer
from dinapoli.io import load_csv
from dinapoli import backtest, plotting

df = load_csv("kgh_d.csv")          # Stooq, Bossa albo dowolny CSV z OHLC
a = Analyzer(df, symbol="KGH")

print(a.snapshot().report())        # stan rynku na dziś
sig = a.signal()                    # sygnał na dziś albo None

signals = a.scan(start=300)         # przejście po historii
trades = backtest.run(a, signals, target="COP", trail_atr=1.5)
print(backtest.stats(trades))

plotting.plot(a, signals=signals, path="kgh.png")
```

Linia poleceń:

```bash
python -m dinapoli.demo                 # dane syntetyczne
python -m dinapoli.demo kgh_d.csv KGH   # własny plik
```

## Architektura

```
config.py        wszystkie parametry w jednym miejscu
swings.py        detekcja fal (zygzak ATR / procentowy / fraktale)
levels.py        zniesienia F3/F5 i zasięgi COP/OP/XOP
confluence.py    silnik Zgodności — klastrowanie poziomów w strefy
indicators.py    DMA, ATR, MACD Predictor, Oscillator Predictor
trend.py         stan trendu per interwał + agregacja D/W/M
setups.py        B&B, DRePo, W&R, odbicie od Zgodności
system.py        Analyzer — spina wszystko, generuje sygnały z SL
backtest.py      prosty backtest zdarzeniowy
plotting.py      wykres w stylu oryginału
io.py            wczytywanie CSV
```

## Jak działa silnik Zgodności

1. Detektor fal zwraca punkty zwrotne osobno dla D, W i M.
2. Z każdej fali liczone są zniesienia, z każdej trójki A-B-C — zasięgi.
3. Wszystkie poziomy ze wszystkich interwałów trafiają do jednego zbioru.
4. Zachłanne okno o szerokości `2 × tolerancja` wycina najgęstsze skupiska.
   Okno ma stałą szerokość — dzięki temu żadna strefa nie rozlewa się na
   kilkanaście procent wykresu, co psuło pierwszą wersję opartą na
   łączeniu łańcuchowym.
5. Strefa dostaje ocenę siły: liczba poziomów, ile różnych fal je dało,
   ile różnych interwałów, z wagą rosnącą dla W i M.

## MACD Predictor — wyprowadzenie

Szukamy ceny `P`, przy której jutro MACD zrówna się z linią sygnału.
Dla `a_x = 2/(x+1)`:

```
MACD' = (a_f - a_s)·P + (1-a_f)·EMAf - (1-a_s)·EMAs
Sig'  = a_g·MACD' + (1-a_g)·Sig

MACD' - Sig' = (1-a_g)·(MACD' - Sig)
```

Czyli przecięcie zachodzi dokładnie wtedy, gdy `MACD' = Sig`. Stąd:

```
P = [ Sig - (1-a_f)·EMAf + (1-a_s)·EMAs ] / (a_f - a_s)
```

Forma zamknięta, bez iteracji. Wartość bywa odległa od rynku, gdy MACD
i sygnał są prawie równoległe — takie odczyty są odcinane, bo poziom
oddalony o kilkanaście ATR nie jest wsparciem.

## Czego tu nie ma i o czym trzeba pamiętać

**Wyniki backtestu na danych syntetycznych nie znaczą nic.** Demo generuje
szum, żeby sprawdzić, czy kod się spina. Ocena reguł wymaga prawdziwych
notowań, kosztów transakcyjnych i testu poza próbą.

**Oscillator Predictor jest rekonstrukcją, nie kopią.** Oryginalna formuła
DiNapoliego jest komercyjna i zamknięta. Tutaj jest odtworzona z tej samej
idei — kwantyle oscylatora zdetrendowanego przełożone z powrotem na cenę.

**Definicja trendu to decyzja projektowa.** Dokument źródłowy nigdzie nie
definiuje, czym jest „trend wzrostowy dzienny". Przyjęto klasykę Dowa
liczoną z wykrytych fal. Zmiana sprowadza się do podmiany `trend.trend_state`.

**Detekcja fal decyduje o wszystkim.** Poziomy Fibo są dokładnie tak dobre,
jak punkty zwrotne, z których je policzono. Warto przetestować `SwingConfig`
na swoim uniwersum, zanim zaufa się sygnałom.

**Backtest nie modeluje realiów.** Brak poślizgu, prowizji, luk otwarcia
i wypełnień. Jedna pozycja naraz, wejście po cenie zamknięcia.

To narzędzie analityczne, nie rekomendacja inwestycyjna.
