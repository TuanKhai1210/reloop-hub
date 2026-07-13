from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import hash_password
from app.main import app
from app.models import (
    Hub,
    HubStatus,
    User,
    UserRole,
    Vehicle,
    Voucher,
    VoucherStatus,
)


pytestmark = pytest.mark.integration


def add_fixture_data(db_session: Session) -> dict:
    token = uuid4().hex[:10].upper()
    admin = User(
        name="API Admin",
        email=f"admin-{token.lower()}@reloop.test",
        hashed_password=hash_password("Admin@123"),
        is_active=True,
        phone=None,
        student_code=None,
        role=UserRole.ADMIN,
        points_balance=0,
        total_bottles_returned=0,
    )
    user = User(
        name="API Student",
        email=f"student-{token.lower()}@reloop.test",
        hashed_password=hash_password("Student@123"),
        is_active=True,
        phone=None,
        student_code=f"API-{token}",
        role=UserRole.USER,
        points_balance=0,
        total_bottles_returned=0,
    )
    driver = User(
        name="API Driver",
        email=f"driver-{token.lower()}@reloop.test",
        hashed_password=hash_password("Driver@123"),
        is_active=True,
        phone=None,
        student_code=None,
        role=UserRole.DRIVER,
        points_balance=0,
        total_bottles_returned=0,
    )
    db_session.add_all([admin, user, driver])
    db_session.flush()

    hub = Hub(
        code=f"API-HUB-{token}",
        name="API Campus Hub",
        location_name="API Test Canteen",
        latitude=Decimal("10.762622"),
        longitude=Decimal("106.660172"),
        status=HubStatus.ACTIVE,
        pet_capacity=1,
        hdpe_capacity=1,
        pet_current=0,
        hdpe_current=0,
        pickup_threshold_percent=100,
        capacity_kg=Decimal("200"),
        current_load_kg=Decimal("0"),
        fill_level=Decimal("0"),
        camera_online=True,
        sensor_online=True,
    )
    voucher = Voucher(
        code=f"API-VOUCHER-{token}",
        name="API Canteen Voucher",
        partner_name="API Canteen",
        description="API integration voucher",
        required_points=10,
        value_text="2,000 VND discount",
        quantity_available=10,
        status=VoucherStatus.ACTIVE,
    )
    db_session.add_all([hub, voucher])
    db_session.flush()
    vehicle = Vehicle(
        code=f"API-TRUCK-{token}",
        driver_id=driver.id,
        capacity_kg=Decimal("500"),
        latitude=Decimal("10.762000"),
        longitude=Decimal("106.660000"),
        active=True,
    )
    db_session.add(vehicle)
    db_session.flush()
    return {
        "admin": admin,
        "user": user,
        "driver": driver,
        "hub": hub,
        "voucher": voucher,
        "vehicle": vehicle,
    }


def auth_headers(
    client: TestClient,
    email: str,
    password: str,
) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/token",
        data={"username": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return {
        "Authorization": (
            f"Bearer {response.json()['access_token']}"
        )
    }


def test_complete_unified_api_flow(db_session: Session) -> None:
    data = add_fixture_data(db_session)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            admin_headers = auth_headers(
                client,
                data["admin"].email,
                "Admin@123",
            )
            user_headers = auth_headers(
                client,
                data["user"].email,
                "Student@123",
            )

            assert client.get("/health").status_code == 200
            assert (
                client.get(
                    "/api/v1/auth/me",
                    headers=user_headers,
                ).json()["role"]
                == "USER"
            )

            telemetry = client.post(
                f"/api/v1/hubs/{data['hub'].code}/telemetry",
                headers={"X-Device-Key": settings.device_api_key},
                json={
                    "fill_level": "0",
                    "weight_kg": "0",
                    "camera_online": True,
                    "sensor_online": True,
                    "temperature_c": "31.5",
                },
            )
            assert telemetry.status_code == 200, telemetry.text

            accepted = client.post(
                "/api/v1/deposits/inspect",
                headers={"X-Device-Key": settings.device_api_key},
                json={
                    "user_id": str(data["user"].id),
                    "hub_code": data["hub"].code,
                    "material_type": "PET",
                    "weight_g": "25",
                    "ai_confidence": "0.97",
                    "cleanliness_score": "0.91",
                    "liquid_detected": False,
                    "foreign_object_detected": False,
                },
            )
            assert accepted.status_code == 201, accepted.text
            assert accepted.json()["machine_action"] == "accept_and_store"
            assert accepted.json()["deposit"]["points_awarded"] == 10
            assert accepted.json()["deposit"]["cleanliness_score"] == "0.9100"
            trace_code = accepted.json()["deposit"]["code"]
            batch_id = accepted.json()["deposit"]["batch_id"]
            session_id = accepted.json()["deposit"]["session_id"]

            rejected = client.post(
                "/api/v1/deposits/inspect",
                headers={"X-Device-Key": settings.device_api_key},
                json={
                    "user_id": str(data["user"].id),
                    "hub_code": data["hub"].code,
                    "material_type": "HDPE",
                    "weight_g": "25",
                    "ai_confidence": "0.98",
                    "cleanliness_score": "0.9",
                    "liquid_detected": True,
                    "foreign_object_detected": False,
                },
            )
            assert rejected.status_code == 201, rejected.text
            assert rejected.json()["machine_action"] == "reject_and_return"

            completed_session = client.post(
                f"/api/v1/deposits/sessions/{session_id}/complete",
                headers=user_headers,
            )
            assert completed_session.status_code == 200
            assert completed_session.json()["status"] == "COMPLETED"

            telemetry_history = client.get(
                f"/api/v1/hubs/{data['hub'].code}/telemetry?period=day",
                headers=admin_headers,
            )
            assert telemetry_history.status_code == 200
            assert len(telemetry_history.json()) == 1

            vouchers = client.get(
                "/api/v1/vouchers", headers=user_headers
            )
            assert vouchers.status_code == 200
            redemption = client.post(
                "/api/v1/vouchers/redeem",
                headers=user_headers,
                json={"voucher_id": str(data["voucher"].id)},
            )
            assert redemption.status_code == 201, redemption.text
            used_redemption = client.post(
                "/api/v1/vouchers/redemptions/"
                f"{redemption.json()['redemption_code']}/use",
                headers=admin_headers,
            )
            assert used_redemption.status_code == 200
            assert used_redemption.json()["status"] == "USED"
            reused_redemption = client.post(
                "/api/v1/vouchers/redemptions/"
                f"{redemption.json()['redemption_code']}/use",
                headers=admin_headers,
            )
            assert reused_redemption.status_code == 409

            optimized = client.post(
                "/api/v1/routes/optimize",
                headers=admin_headers,
                json={
                    "vehicle_id": str(data["vehicle"].id),
                    "fill_threshold": 1,
                },
            )
            assert optimized.status_code == 201, optimized.text
            route = optimized.json()
            assert len(route["stops"]) == 1

            started = client.post(
                f"/api/v1/routes/{route['id']}/start",
                headers=admin_headers,
            )
            assert started.status_code == 200, started.text
            stop = route["stops"][0]
            picked = client.post(
                f"/api/v1/routes/{route['id']}/stops/{stop['id']}/pickup",
                headers=admin_headers,
                json={"collected_load_kg": "0.025"},
            )
            assert picked.status_code == 200, picked.text
            completed = client.post(
                f"/api/v1/routes/{route['id']}/complete",
                headers=admin_headers,
            )
            assert completed.status_code == 200, completed.text
            assert completed.json()["status"] == "COMPLETED"

            receipt = client.post(
                f"/api/v1/traceability/batches/{batch_id}/receive",
                headers=admin_headers,
                json={
                    "facility_code": "RECYCLER-DEMO-01",
                    "received_weight_kg": "0.025",
                    "notes": "API integration receipt",
                },
            )
            assert receipt.status_code == 200, receipt.text
            assert receipt.json()["status"] == "RECEIVED"
            assert receipt.json()["trace_events_created"] == 1
            duplicate_receipt = client.post(
                f"/api/v1/traceability/batches/{batch_id}/receive",
                headers=admin_headers,
                json={
                    "facility_code": "RECYCLER-DEMO-01",
                    "received_weight_kg": "0.025",
                },
            )
            assert duplicate_receipt.status_code == 409

            trace = client.get(
                f"/api/v1/traceability/{trace_code}",
                headers=admin_headers,
            )
            assert trace.status_code == 200, trace.text
            assert trace.json()["current_stage"] == "RECEIVED"

            summary = client.get(
                "/api/v1/dashboard/summary?period=week",
                headers=admin_headers,
            )
            assert summary.status_code == 200, summary.text
            assert summary.json()["period"] == "week"
            assert summary.json()["participants"] == 1
            assert summary.json()["successful_transactions"] == 1
            assert summary.json()["accepted_bottles"] == 1
            assert summary.json()["rejected_bottles"] == 1
            assert summary.json()["success_rate_percent"] == "50.00"
            assert summary.json()["distance_saved_km"] != "0.00"
            assert (
                summary.json()["traceability_completeness_percent"]
                == "100.00"
            )

            denied_summary = client.get(
                "/api/v1/dashboard/summary",
                headers=user_headers,
            )
            assert denied_summary.status_code == 403

            report = client.get(
                "/api/v1/reports/esg?period=month",
                headers=admin_headers,
            )
            assert report.status_code == 200, report.text
            assert report.json()["period"] == "month"
            assert report.json()["pet_bottles"] == 1
            assert report.json()["completed_routes"] == 1
            assert report.json()["participants"] == 1
            assert report.json()["co2_methodology_version"]
    finally:
        app.dependency_overrides.clear()


def test_device_endpoint_requires_api_key(
    db_session: Session,
) -> None:
    data = add_fixture_data(db_session)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            response = client.post(
                f"/api/v1/hubs/{data['hub'].code}/telemetry",
                json={
                    "fill_level": 10,
                    "weight_kg": 20,
                    "camera_online": True,
                    "sensor_online": True,
                },
            )
            assert response.status_code == 401
    finally:
        app.dependency_overrides.clear()
