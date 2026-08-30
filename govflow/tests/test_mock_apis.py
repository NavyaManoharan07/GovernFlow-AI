from fastapi.testclient import TestClient

from backend.main import app


def test_health_endpoint():
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"


def test_clean_scenario_progresses_to_approved():
    with TestClient(app) as client:
        submit = client.post(
            "/mock/business-registration",
            json={"business_name": "Sunrise Foods", "scenario": "clean"},
        )
        assert submit.status_code == 200
        body = submit.json()
        assert body["status"] == "SUBMITTED"
        assert body["MOCK_DATA"] is True
        application_id = body["application_id"]

        poll_1 = client.get(f"/mock/application/{application_id}")
        assert poll_1.json()["status"] == "PENDING"

        poll_2 = client.get(f"/mock/application/{application_id}")
        assert poll_2.json()["status"] == "APPROVED"


def test_document_missing_scenario():
    with TestClient(app) as client:
        submit = client.post(
            "/mock/food-license",
            json={"business_name": "Test Co", "scenario": "document_missing"},
        )
        application_id = submit.json()["application_id"]

        poll = client.get(f"/mock/application/{application_id}")
        assert poll.json()["status"] == "DOCUMENT_MISSING"


def test_rejected_scenario():
    with TestClient(app) as client:
        submit = client.post(
            "/mock/tax-registration",
            json={"business_name": "Test Co", "scenario": "rejected"},
        )
        application_id = submit.json()["application_id"]

        poll_1 = client.get(f"/mock/application/{application_id}")
        assert poll_1.json()["status"] == "PENDING"

        poll_2 = client.get(f"/mock/application/{application_id}")
        assert poll_2.json()["status"] == "REJECTED"


def test_transient_failure_then_success_scenario():
    with TestClient(app) as client:
        submit = client.post(
            "/mock/local-approval",
            json={"business_name": "Test Co", "scenario": "transient_failure"},
        )
        application_id = submit.json()["application_id"]

        poll_1 = client.get(f"/mock/application/{application_id}")
        assert poll_1.status_code == 503

        poll_2 = client.get(f"/mock/application/{application_id}")
        assert poll_2.status_code == 200
        assert poll_2.json()["status"] == "APPROVED"


def test_document_validation_endpoint():
    with TestClient(app) as client:
        valid = client.post(
            "/mock/document-validation",
            json={"documents": ["id_proof.pdf"], "scenario": "clean"},
        )
        assert valid.json()["valid"] is True

        invalid = client.post(
            "/mock/document-validation",
            json={"documents": [], "scenario": "document_missing"},
        )
        assert invalid.json()["valid"] is False
        assert len(invalid.json()["missing_documents"]) > 0
