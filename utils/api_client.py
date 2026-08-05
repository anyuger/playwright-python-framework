import os
import requests
from dotenv import load_dotenv

load_dotenv()


class APIClient:
    BASE_URL = "https://reqres.in/api"

    def __init__(self):
        api_key = os.getenv("REQRES_API_KEY", "")
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "x-api-key": api_key
        })

    def get_users(self, page: int = 1) -> dict:
        response = self.session.get(f"{self.BASE_URL}/users", params={"page": page})
        response.raise_for_status()
        return response.json()

    def get_user(self, user_id: int) -> dict:
        response = self.session.get(f"{self.BASE_URL}/users/{user_id}")
        response.raise_for_status()
        return response.json()

    def create_user(self, name: str, job: str) -> dict:
        payload = {"name": name, "job": job}
        response = self.session.post(f"{self.BASE_URL}/users", json=payload)
        response.raise_for_status()
        return response.json()

    def update_user(self, user_id: int, name: str, job: str) -> dict:
        payload = {"name": name, "job": job}
        response = self.session.put(f"{self.BASE_URL}/users/{user_id}", json=payload)
        response.raise_for_status()
        return response.json()

    def delete_user(self, user_id: int) -> int:
        response = self.session.delete(f"{self.BASE_URL}/users/{user_id}")
        return response.status_code