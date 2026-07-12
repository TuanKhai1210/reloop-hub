from fastapi.testclient import TestClient


def test_health_and_auth(client: TestClient, admin_headers: dict):
    assert client.get("/health").json()["status"] == "ok"
    me = client.get("/api/v1/auth/me", headers=admin_headers)
    assert me.status_code == 200
    assert me.json()["role"] == "admin"


def test_realtime_telemetry_and_quality_control(client: TestClient, admin_headers: dict):
    telemetry = client.post(
        "/api/v1/hubs/HUB-UEH-01/telemetry",
        headers={"X-Device-Key": "test-device-key"},
        json={
            "fill_level": 82,
            "weight_kg": 164,
            "camera_online": True,
            "sensor_online": True,
            "temperature_c": 31.5,
        },
    )
    assert telemetry.status_code == 200
    assert telemetry.json()["status"] == "online"

    accepted = client.post(
        "/api/v1/deposits/inspect",
        headers={"X-Device-Key": "test-device-key"},
        json={
            "user_id": 2,
            "hub_code": "HUB-UEH-01",
            "material_type": "PET",
            "weight_g": 120,
            "ai_confidence": 0.97,
            "cleanliness_score": 0.91,
            "liquid_detected": False,
            "foreign_object_detected": False,
        },
    )
    assert accepted.status_code == 201
    assert accepted.json()["machine_action"] == "accept_and_store"
    assert accepted.json()["deposit"]["points_earned"] > 0

    rejected = client.post(
        "/api/v1/deposits/inspect",
        headers={"X-Device-Key": "test-device-key"},
        json={
            "user_id": 2,
            "hub_code": "HUB-UEH-01",
            "material_type": "HDPE",
            "weight_g": 90,
            "ai_confidence": 0.98,
            "cleanliness_score": 0.9,
            "liquid_detected": True,
            "foreign_object_detected": False,
        },
    )
    assert rejected.status_code == 201
    assert rejected.json()["machine_action"] == "reject_and_return"
    assert "chất lỏng" in rejected.json()["user_message"]

    summary = client.get("/api/v1/dashboard/summary", headers=admin_headers)
    assert summary.status_code == 200
    assert summary.json()["transactions_today"] >= 1

    users = client.get("/api/v1/users?role=resident", headers=admin_headers)
    assert users.status_code == 200
    assert users.json()[0]["email"] == "student@reloop.vn"

    resident_login = client.post(
        "/api/v1/auth/token",
        data={"username": "student@reloop.vn", "password": "Student@123"},
    ).json()
    redeemed = client.post(
        "/api/v1/users/me/rewards/redeem",
        headers={"Authorization": f"Bearer {resident_login['access_token']}"},
        json={"points": 1, "reward_name": "Voucher demo", "payout_channel": "voucher"},
    )
    assert redeemed.status_code == 201
    assert redeemed.json()["points"] == -1


def test_route_traceability_and_esg(client: TestClient, admin_headers: dict):
    deposits = client.get("/api/v1/deposits?status=accepted", headers=admin_headers).json()
    trace_code = deposits[0]["trace_code"]

    optimized = client.post(
        "/api/v1/routes/optimize",
        headers=admin_headers,
        json={"vehicle_id": 1, "fill_threshold": 70},
    )
    assert optimized.status_code == 201, optimized.text
    route = optimized.json()
    assert route["stops"]
    assert route["total_distance_km"] <= route["baseline_distance_km"]

    started = client.post(f"/api/v1/routes/{route['id']}/start", headers=admin_headers)
    assert started.status_code == 200
    for stop in route["stops"]:
        picked = client.post(
            f"/api/v1/routes/{route['id']}/stops/{stop['id']}/pickup",
            headers=admin_headers,
            json={"collected_load_kg": stop["expected_load_kg"]},
        )
        assert picked.status_code == 200, picked.text

    completed = client.post(f"/api/v1/routes/{route['id']}/complete", headers=admin_headers)
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"

    trace = client.get(f"/api/v1/traceability/{trace_code}", headers=admin_headers)
    assert trace.status_code == 200
    assert trace.json()["current_stage"] in {"hub_stored", "picked_up"}

    report = client.get("/api/v1/reports/esg?period=day", headers=admin_headers)
    assert report.status_code == 200
    assert report.json()["total_plastic_recovered_kg"] > 0
    assert report.json()["completed_routes"] >= 1


def test_device_endpoints_are_protected(client: TestClient):
    response = client.post(
        "/api/v1/hubs/HUB-UEH-01/telemetry",
        json={"fill_level": 10, "weight_kg": 20, "camera_online": True, "sensor_online": True},
    )
    assert response.status_code == 401
