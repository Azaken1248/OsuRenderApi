import io
import pytest
from unittest.mock import patch, MagicMock
from src.core.storage import StorageClient


@patch("src.core.storage.Minio")
def test_storage_client_initialization(mock_minio):
    mock_instance = mock_minio.return_value
    mock_instance.bucket_exists.return_value = False

    client = StorageClient()

    mock_instance.bucket_exists.assert_called_once()
    mock_instance.make_bucket.assert_called_once_with(client.bucket)


@patch("src.core.storage.Minio")
def test_storage_upload_file(mock_minio):
    mock_instance = mock_minio.return_value
    client = StorageClient()

    content = b"dummy content"
    client.upload_file("test/file.txt", content, len(content), "text/plain")

    mock_instance.put_object.assert_called_once()
    args, kwargs = mock_instance.put_object.call_args
    assert kwargs["bucket_name"] == client.bucket
    assert kwargs["object_name"] == "test/file.txt"
    assert kwargs["length"] == len(content)
    assert kwargs["content_type"] == "text/plain"


@patch("src.core.storage.Minio")
def test_storage_presigned_url(mock_minio):
    mock_instance = mock_minio.return_value
    mock_instance.presigned_get_object.return_value = "http://mock-url/test/file.txt"

    client = StorageClient()
    url = client.get_presigned_url("test/file.txt")

    assert url == "http://mock-url/test/file.txt"
    mock_instance.presigned_get_object.assert_called_once_with(
        bucket_name=client.bucket, object_name="test/file.txt"
    )
