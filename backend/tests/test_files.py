def test_upload_file_success(client, mock_user_token):
    # Mock file upload
    files = {'file': ('test_doc.txt', b'This is a test content for RAG', 'text/plain')}
    
    response = client.post(
        "/api/upload",
        headers={"Authorization": f"Bearer {mock_user_token}"},
        files=files
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "test_doc.txt"
    assert "id" in data
    assert data["is_indexed"] is False  # Should be false initially before processing

def test_list_files_empty(client, mock_user_token):
    response = client.get(
        "/api/files",
        headers={"Authorization": f"Bearer {mock_user_token}"}
    )
    assert response.status_code == 200
    assert response.json() == []

def test_delete_file_not_found(client, mock_user_token):
    response = client.delete(
        "/api/delete/99999",
        headers={"Authorization": f"Bearer {mock_user_token}"}
    )
    assert response.status_code == 404
