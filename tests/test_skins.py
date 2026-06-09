import pytest
from httpx import AsyncClient, ASGITransport
from src.api.app import create_app
from unittest.mock import patch, MagicMock

app = create_app()

@pytest.mark.asyncio(loop_scope="session")
async def test_list_skins():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/skins")
        assert response.status_code == 200
        assert response.json() == []

@pytest.mark.asyncio(loop_scope="session")
async def test_upload_skin():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {
            "skin": ("test_skin.osk", b"dummy data", "application/octet-stream")
        }
        
        with patch("src.api.routes.skins.storage_client") as mock_storage:
            response = await client.post("/v1/skins/upload", files=files)
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["skin_name"] == "test_skin"
            mock_storage.upload_file.assert_called_once()
