from unittest.mock import Mock, patch

from backend.knowledge_service import _upload_original


@patch("backend.knowledge_service.requests.post")
def test_upload_original_uses_private_storage_rest_api(mock_post, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-key")
    monkeypatch.setenv("SUPABASE_KNOWLEDGE_BUCKET", "knowledge-originals")
    response = Mock()
    mock_post.return_value = response

    storage_path = _upload_original(
        tenant_id=7,
        document_id="doc-id",
        filename="Informe: revisión #1.pdf",
        content=b"%PDF-1.7",
        mime_type="application/pdf",
    )

    assert storage_path == "tenant/7/knowledge/doc-id/original.pdf"
    response.raise_for_status.assert_called_once()
    mock_post.assert_called_once_with(
        "https://project.supabase.co/storage/v1/object/knowledge-originals/tenant/7/knowledge/doc-id/original.pdf",
        headers={
            "apikey": "service-key",
            "Authorization": "Bearer service-key",
            "content-type": "application/pdf",
            "x-upsert": "true",
        },
        data=b"%PDF-1.7",
        timeout=30,
    )
