import os
import tempfile

from fastapi.testclient import TestClient

from chat_guardian.api.app import create_app
from chat_guardian.settings import settings


def test_setup_status_and_setup_flow() -> None:
    # Use isolated sqlite database for this test
    tmp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".sqlite")
    tmp_db.close()
    original_db = settings.database_url
    settings.database_url = f"sqlite:///{tmp_db.name}"

    try:
        app = create_app()
        client = TestClient(app)

        status_resp = client.get("/auth/setup-status")
        assert status_resp.status_code == 200
        assert status_resp.json()["setup_required"] is True

        setup_resp = client.post(
            "/auth/setup",
            json={"username": "admin_test", "password": "pass123"},
        )
        assert setup_resp.status_code == 200
        setup_data = setup_resp.json()
        assert setup_data["setup_required"] is False
        token = setup_data["token"]

        status_after = client.get("/auth/setup-status")
        assert status_after.status_code == 200
        assert status_after.json()["setup_required"] is False

        headers = {"Authorization": f"Bearer {token}"}
        authed_resp = client.get("/api/settings", headers=headers)
        assert authed_resp.status_code == 200

        # login should also work with newly set credentials
        login_resp = client.post("/auth/login", json={"username": "admin_test", "password": "pass123"})
        assert login_resp.status_code == 200
    finally:
        settings.database_url = original_db
        os.remove(tmp_db.name)
