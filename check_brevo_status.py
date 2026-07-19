import getpass
import json
import requests

api_key = getpass.getpass("Paste the same Brevo API key: ")

response = requests.get(
    "https://api.brevo.com/v3/smtp/statistics/events",
    headers={
        "accept": "application/json",
        "api-key": api_key,
    },
    params={
        "email": "nourbenhnia619@gmail.com",
        "limit": 20,
        "sort": "desc",
    },
    timeout=30,
)

print("HTTP:", response.status_code)
print(json.dumps(response.json(), indent=2, ensure_ascii=False))
