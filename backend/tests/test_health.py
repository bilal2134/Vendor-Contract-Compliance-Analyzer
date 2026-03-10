import os

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_healthcheck() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_playbook_and_package_ingestion_flow() -> None:
    playbook_response = client.post(
        "/api/ingestion/playbooks/upload",
        data={
            "name": "Test Procurement Playbook",
            "effective_date": "2026-03-09",
            "description": "Test playbook",
        },
        files={
            "file": (
                "playbook.txt",
                # random salt ensures a unique SHA-256 each test run → no dedup collision
                os.urandom(8) + b"4.2.1 Cyber Liability Vendors must maintain at least $5000000 cyber liability coverage and reference it in the DPA. 5.4.3 Data retention Vendors must document retention and deletion timelines.",
                "text/plain",
            ),
        },
    )

    assert playbook_response.status_code == 201
    version_id = playbook_response.json()["version_id"]

    package_response = client.post(
        "/api/ingestion/packages/upload",
        data={
            "vendor_name": "Northstar Cloud Systems",
            "playbook_version_id": version_id,
        },
        files={
            "msa": ("msa.txt", b"Either party may terminate on 30 days written notice.", "text/plain"),
            "dpa": ("dpa.txt", b"This DPA describes data processing but does not mention insurance.", "text/plain"),
            "insurance": ("insurance.txt", b"Cyber liability coverage: $5000000 aggregate.", "text/plain"),
            "profile": ("profile.txt", b"Standard customer notice period is 60 days before termination.", "text/plain"),
        },
    )

    assert package_response.status_code == 201
    report_id = package_response.json()["report_id"]

    report_response = client.get(f"/api/reports/{report_id}")
    assert report_response.status_code == 200
    payload = report_response.json()
    assert payload["findings"]
    assert payload["conflicts"]
