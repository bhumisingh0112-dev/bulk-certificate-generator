from pathlib import Path


def test_create_generation_job(client, valid_payload):
    response = client.post("/api/jobs", json=valid_payload)
    assert response.status_code == 202
    body = response.json()
    assert body["total_count"] == 2
    assert body["status"] == "PENDING"
    assert body["success_count"] == 0

    detail = client.get(f"/api/jobs/{body['id']}")
    assert detail.status_code == 200
    assert detail.json()["status"] == "COMPLETED"
    assert detail.json()["success_count"] == 2


def test_request_level_input_validation(client, valid_payload):
    invalid = dict(valid_payload)
    invalid["recipients"] = []
    response = client.post("/api/jobs", json=invalid)
    assert response.status_code == 422


def test_invalid_recipient_does_not_block_valid_recipient(client, valid_payload):
    valid_payload["recipients"][0]["email"] = "not-an-email"
    response = client.post("/api/jobs", json=valid_payload)
    assert response.status_code == 202
    job_id = response.json()["id"]

    detail = client.get(f"/api/jobs/{job_id}").json()
    assert detail["status"] == "COMPLETED_WITH_ERRORS"
    assert detail["success_count"] == 1
    assert detail["failed_count"] == 1
    assert any(r["status"] == "FAILED" for r in detail["recipients"])
    assert any(r["status"] == "SUCCESS" for r in detail["recipients"])


def test_certificate_generation_and_retrieval(client, valid_payload):
    response = client.post("/api/jobs", json=valid_payload)
    job_id = response.json()["id"]

    certificate_list = client.get(f"/api/jobs/{job_id}/certificates")
    assert certificate_list.status_code == 200
    data = certificate_list.json()
    assert data["count"] == 2

    recipient_id = data["certificates"][0]["id"]
    download = client.get(f"/api/certificates/{recipient_id}/download")
    assert download.status_code == 200
    assert download.headers["content-type"] == "application/pdf"
    assert download.content.startswith(b"%PDF")


def test_job_status_and_progress(client, valid_payload):
    response = client.post("/api/jobs", json=valid_payload)
    job_id = response.json()["id"]
    detail = client.get(f"/api/jobs/{job_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["total_count"] == 2
    assert body["success_count"] + body["failed_count"] == 2
    assert body["status"] in {"COMPLETED", "COMPLETED_WITH_ERRORS", "FAILED"}


def test_individual_generation_failure_is_isolated(client, valid_payload, monkeypatch):
    from app.services import job_service

    real_generate = job_service.generate_certificate
    calls = {"count": 0}

    def flaky_generate(**kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("simulated renderer failure")
        return real_generate(**kwargs)

    monkeypatch.setattr(job_service, "generate_certificate", flaky_generate)

    response = client.post("/api/jobs", json=valid_payload)
    job_id = response.json()["id"]
    detail = client.get(f"/api/jobs/{job_id}").json()

    assert detail["status"] == "COMPLETED_WITH_ERRORS"
    assert detail["success_count"] == 1
    assert detail["failed_count"] == 1
    assert any("simulated renderer failure" in (r["error_message"] or "") for r in detail["recipients"])


def test_bulk_zip_download(client, valid_payload):
    response = client.post("/api/jobs", json=valid_payload)
    job_id = response.json()["id"]
    download = client.get(f"/api/jobs/{job_id}/download")
    assert download.status_code == 200
    assert download.headers["content-type"] == "application/zip"
    assert download.content[:2] == b"PK"
