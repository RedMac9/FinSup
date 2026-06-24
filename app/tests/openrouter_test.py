import os
import requests
from dotenv import load_dotenv


secrets_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "secrets.env")
)
load_dotenv(secrets_path)


def test_openrouter_recommendation():
    ticker_org = "AAPL"
    market = "NASDAQ"

    prompt = (
        f"Przygotuj rekomendację na podstawie rekomendacji giełdowych i bieżącej analizy "
        f"wiadomości gospodarczych dla spółki {ticker_org} ({market}) w horyzoncie 30 dni "
        f"w skali 0-6 (sprzedaj-trzymaj). "
        f"Podaj wiodące źródło informacji. "
        f"Zwróć odpowiedź wyłącznie w formacie: liczba,uzasadnienie,źródło. "
        f"W źródle podaj linki i daty publikacji. "
        f"Nie bierz pod uwagę informacji starszych niż 20 dni od teraz."
        f"Oszacuj cenę akcji"
    )

    print(f"Requesting AI recommendation for {ticker_org} from OpenRouter...")

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("Error: OPENROUTER_API_KEY not found in environment.")
        return

    payload = {
        "model": "google/gemini-3.1-flash-lite-preview:online",
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.1,
        "max_tokens": 550
    }

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://your-app.example",
                "X-OpenRouter-Title": "FinRep2"
            },
            json=payload,
            timeout=60
        )

        print("STATUS:", response.status_code)
        print("BODY:", response.text)

        response.raise_for_status()

        data = response.json()

        if "choices" in data and data["choices"]:
            recommendation = data["choices"][0]["message"]["content"].strip()
            print("Recommendation:")
            print(recommendation)
        else:
            print(f"Unexpected response format: {data}")

    except requests.HTTPError as e:
        print(f"HTTP error: {e}")
    except Exception as e:
        print(f"Error getting OpenRouter recommendation: {e}")


if __name__ == "__main__":
    test_openrouter_recommendation()
