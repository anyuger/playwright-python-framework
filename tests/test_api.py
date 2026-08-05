import pytest
from utils.api_client import APIClient


class TestAPI:

    @pytest.fixture(autouse=True)
    def api_client(self):
        self.client = APIClient()

    def test_get_users_returns_200(self):
        response = self.client.get_users(page=1)
        assert response["page"] == 1
        assert len(response["data"]) > 0

    def test_get_users_second_page(self):
        response = self.client.get_users(page=2)
        assert response["page"] == 2
        assert len(response["data"]) > 0

    def test_get_single_user(self):
        response = self.client.get_user(user_id=2)
        assert response["data"]["id"] == 2
        assert "email" in response["data"]
        assert "first_name" in response["data"]
        assert "last_name" in response["data"]

    def test_create_user(self):
        response = self.client.create_user(name="Anton", job="QA Lead")
        assert response["name"] == "Anton"
        assert response["job"] == "QA Lead"
        assert "id" in response
        assert "createdAt" in response

    def test_update_user(self):
        response = self.client.update_user(user_id=2, name="Anton", job="Senior SDET")
        assert response["name"] == "Anton"
        assert response["job"] == "Senior SDET"
        assert "updatedAt" in response

    def test_delete_user(self):
        status_code = self.client.delete_user(user_id=2)
        assert status_code == 204

    def test_get_nonexistent_user(self):
        with pytest.raises(Exception):
            self.client.get_user(user_id=9999)