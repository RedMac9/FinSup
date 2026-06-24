# Wdrożenie FinSup2 na mikr.us (srv36) + Cytrus + domena fivereps.com

Architektura:

```
Przeglądarka → https://finsup.fivereps.com → [Cytrus: TLS] → srv36.mikr.us:20321 → Gunicorn → Flask
```

- VPS: mikr.us srv36, Ubuntu 22.04, port aplikacji **20321**
- HTTPS: Cytrus (Let's Encrypt, automatycznie)
- Brak nginx i certbota — Cytrus jest reverse proxy

---

## Etap 1 — DNS w OVH

W panelu OVH → strefa DNS `fivereps.com` dodaj rekord **A**:

| Typ | Subdomena | Wartość (cel) |
|-----|-----------|---------------|
| A   | `finsup`  | `135.181.95.85` |

(To IP frontendu Cytrus wg dokumentacji mikr.us.)

Poczekaj na propagację. Sprawdź lokalnie:

```bash
nslookup finsup.fivereps.com
# powinno zwrócić 135.181.95.85
```

Dopiero gdy DNS wskazuje na `135.181.95.85`, zamawiaj certyfikat w Cytrus (inaczej Let's Encrypt się nie zweryfikuje).

---

## Etap 2 — Konfiguracja serwera (jako root, przez SSH)

```bash
# Aktualizacja + pakiety
apt update && apt upgrade -y
apt install -y python3-venv python3-pip git

# Dedykowany użytkownik (bez logowania, bez sudo)
adduser --system --group --home /opt/finsup finsup

# Kod aplikacji (podstaw swój URL repo)
git clone <URL_TWOJEGO_REPO> /opt/finsup
chown -R finsup:finsup /opt/finsup

# Virtualenv + zależności
python3 -m venv /opt/finsup/venv
/opt/finsup/venv/bin/pip install --upgrade pip
/opt/finsup/venv/bin/pip install -r /opt/finsup/requirements.txt
```

> Uwaga: `psycopg2` może wymagać kompilacji. Jeśli `pip install` na nim padnie,
> zainstaluj nagłówki: `apt install -y libpq-dev gcc python3-dev` i powtórz pip,
> albo zmień w requirements.txt `psycopg2` na `psycopg2-binary`.

---

## Etap 3 — Sekrety (NIE są w gicie)

Pliki `secrets.env` i `secrets/*.json` są w `.gitignore`, więc wgraj je ręcznie.
Z lokalnego komputera (PowerShell / scp), do katalogu `FinRep2/` na serwerze:

```bash
scp secrets.env        root@srv36.mikr.us:/opt/finsup/secrets.env
scp -r secrets          root@srv36.mikr.us:/opt/finsup/secrets
```

Na serwerze ustaw właściciela i restrykcyjne uprawnienia:

```bash
chown -R finsup:finsup /opt/finsup/secrets.env /opt/finsup/secrets
chmod 600 /opt/finsup/secrets.env
chmod 600 /opt/finsup/secrets/*.json
```

Upewnij się, że `secrets.env` zawiera (inaczej aplikacja nie wstanie):
`APP_SECRET_KEY`, `APP_USERNAME`, `APP_PASSWORD`.

### Hashowanie hasła (zalecane zamiast plain text)

Wygeneruj hash i wklej go jako `APP_PASSWORD` w `secrets.env`:

```bash
/opt/finsup/venv/bin/python /opt/finsup/app/hash_password.py
# Podaj hasło dwukrotnie. Skopiuj całą linię, np.:
#   APP_PASSWORD=scrypt:32768:8:1$....
# i podmień nią APP_PASSWORD w secrets.env
nano /opt/finsup/secrets.env
```

`verify_password()` w `flask_app.py` automatycznie wykrywa hash, więc żadne
hasło w czystym tekście nie leży na serwerze.

Wskazówka na `APP_SECRET_KEY` (jeśli jeszcze go nie masz, wygeneruj losowy):

```bash
/opt/finsup/venv/bin/python -c "import secrets; print('APP_SECRET_KEY=' + secrets.token_hex(32))"
```

---

## Etap 4 — Usługa systemd

```bash
cp /opt/finsup/deploy/finsup.service /etc/systemd/system/finsup.service
systemctl daemon-reload
systemctl enable --now finsup

# Status i logi
systemctl status finsup
journalctl -u finsup -f
```

Test lokalny na serwerze (przed Cytrusem):

```bash
curl -i http://127.0.0.1:20321/login    # powinno zwrócić 200 i stronę logowania
```

---

## Etap 5 — Cytrus (HTTPS)

W panelu Cytrus dodaj wpis:

| Pole | Wartość |
|------|---------|
| Nazwa domeny / subdomeny | `finsup.fivereps.com` |
| Gdzie podpiąć (katalog/port) | `http://srv36.mikr.us:20321` |
| Wsparcie dla przekierowań (WP) | **nie** |
| Listowanie plików | **nie** |
| Zamów certyfikat SSL (Let's Encrypt) | **tak** |
| .htaccess / wersja PHP | bez znaczenia |

Po zapisaniu Cytrus pobierze certyfikat (DNS musi już działać — patrz Etap 1).

---

## Etap 6 — Weryfikacja

1. `https://finsup.fivereps.com` → strona logowania, kłódka HTTPS ważna.
2. Logowanie działa (po zalogowaniu sesja się utrzymuje — cookie Secure OK za HTTPS).
3. Po 3. błędnym logowaniu z rzędu rate limiter zaczyna odrzucać (limit 10/min).
4. Błąd serwera nie pokazuje traceback (debug wyłączony).

---

## Etap 7 — (opcjonalnie) odcięcie bezpośredniego plain-HTTP firewallem

Port `20321` jest publicznie osiągalny po nieszyfrowanym HTTP
(`http://srv36.mikr.us:20321`). Można ograniczyć go tak, by ruch przyjmować
tylko od frontendu Cytrus (`135.181.95.85`), a cała reszta szła odrzucona.

> ⚠️ **RYZYKO — przeczytaj zanim uruchomisz.**
> 1. **Lockout SSH:** włączenie `ufw` z domyślną polityką „deny incoming"
>    zablokuje też SSH, jeśli najpierw nie dopuścisz portu SSH. Sprawdź swój
>    port SSH w panelu mikr.us i podstaw go za `<PORT_SSH>`.
> 2. **LXC:** na kontenerach LXC `ufw`/iptables bywa ograniczony — komendy mogą
>    nie zadziałać lub nie mieć efektu.
> 3. **NAT:** mikr.us może NAT-ować połączenie z Cytrusa, więc kontener może
>    widzieć inne źródłowe IP niż `135.181.95.85`. Wtedy reguła „allow from"
>    odetnie też Cytrus i strona przestanie działać.
>
> Dlatego: **NIE zamykaj bieżącej sesji SSH**, otwórz **drugą** sesję do testu,
> i po włączeniu od razu sprawdź `https://finsup.fivereps.com`. Jeśli strona
> padnie — cofnij regułę (`ufw disable`).

```bash
apt install -y ufw

# 1) KONIECZNIE najpierw dopuść SSH (podstaw swój port z panelu mikr.us!)
ufw allow <PORT_SSH>/tcp

# 2) Dopuść Cytrus do portu aplikacji, odrzuć resztę ruchu na 20321
ufw allow from 135.181.95.85 to any port 20321 proto tcp
ufw deny 20321/tcp

# 3) Włącz (ruch wychodzący: yfinance/NBP/Google/DB pozostaje dozwolony)
ufw --force enable
ufw status verbose
```

**Test natychmiast po włączeniu (z drugiej sesji / przeglądarki):**

- `https://finsup.fivereps.com` → nadal działa  ✅
- `http://srv36.mikr.us:20321` → brak odpowiedzi / timeout  ✅

**Jeśli strona padła** (Cytrus przychodzi z innego IP przez NAT) — cofnij:

```bash
ufw disable
```

…i wróćmy do tematu: ustalimy realne źródłowe IP upstreamu i dostosujemy regułę,
albo zostawimy zabezpieczenie na poziomie aplikacji (cookie `Secure` + logowanie),
które i tak już działa.

## Aktualizacje w przyszłości

```bash
cd /opt/finsup && git pull
/opt/finsup/venv/bin/pip install -r /opt/finsup/requirements.txt   # gdy zmienią się zależności
systemctl restart finsup
```

## Uwaga o pamięci (1 GB RAM, brak swap)

Procedury pobierające dane (np. S&P500) mogą zużyć dużo RAM i zostać ubite przez
OOM. Jeśli to wystąpi (`journalctl -u finsup` pokaże `Killed`/restart), wróćmy do
tematu — opcje: uruchamianie ciężkich procedur z CLI poza usługą, ograniczenie
liczby tickerów, albo większy plan VPS.
