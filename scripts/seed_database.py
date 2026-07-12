from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import (
    Hub,
    HubStatus,
    User,
    UserRole,
    Voucher,
    VoucherStatus,
    Vehicle,
)


STUDENT_ID = UUID("00000000-0000-0000-0000-000000000001")
ADMIN_ID = UUID("00000000-0000-0000-0000-000000000002")
DRIVER_ID = UUID("00000000-0000-0000-0000-000000000003")
HUB_ID = UUID("00000000-0000-0000-0000-000000000101")
VOUCHER_2K_ID = UUID("00000000-0000-0000-0000-000000000201")
VOUCHER_5K_ID = UUID("00000000-0000-0000-0000-000000000202")
VEHICLE_ID = UUID("00000000-0000-0000-0000-000000000301")


def add_if_missing(
    session: Session,
    model: type[Any],
    record_id: UUID,
    **values: Any,
) -> bool:
    if session.get(model, record_id) is not None:
        return False

    session.add(
        model(
            id=record_id,
            **values,
        )
    )
    return True


def main() -> None:
    with SessionLocal.begin() as session:
        results = [
            add_if_missing(
                session,
                User,
                STUDENT_ID,
                name="Demo Student",
                email="student@reloop.vn",
                hashed_password=hash_password("Student@123"),
                is_active=True,
                phone="0000000001",
                student_code="DEMO-STUDENT-001",
                role=UserRole.USER,
                points_balance=0,
                total_bottles_returned=0,
            ),
            add_if_missing(
                session,
                User,
                ADMIN_ID,
                name="Demo Admin",
                email="admin@reloop.vn",
                hashed_password=hash_password("Admin@123"),
                is_active=True,
                phone="0000000002",
                student_code=None,
                role=UserRole.ADMIN,
                points_balance=0,
                total_bottles_returned=0,
            ),
            add_if_missing(
                session,
                User,
                DRIVER_ID,
                name="Demo Driver",
                email="driver@reloop.vn",
                hashed_password=hash_password("Driver@123"),
                is_active=True,
                phone="0000000003",
                student_code=None,
                role=UserRole.DRIVER,
                points_balance=0,
                total_bottles_returned=0,
            ),
            add_if_missing(
                session,
                Hub,
                HUB_ID,
                code="HUB-CANTEEN-01",
                name="Campus Canteen Hub",
                location_name="Campus Canteen",
                status=HubStatus.ACTIVE,
                pet_capacity=50,
                hdpe_capacity=30,
                pet_current=0,
                hdpe_current=0,
                pickup_threshold_percent=80,
                capacity_kg=200,
                current_load_kg=0,
                fill_level=0,
                camera_online=True,
                sensor_online=True,
            ),
            add_if_missing(
                session,
                Voucher,
                VOUCHER_2K_ID,
                code="CANTEEN-2K",
                name="2,000 VND Canteen Voucher",
                partner_name="Campus Canteen",
                description="Demo voucher for the ReLoop Hub pilot.",
                required_points=50,
                value_text="2,000 VND discount",
                quantity_available=100,
                status=VoucherStatus.ACTIVE,
            ),
            add_if_missing(
                session,
                Voucher,
                VOUCHER_5K_ID,
                code="CANTEEN-5K",
                name="5,000 VND Canteen Voucher",
                partner_name="Campus Canteen",
                description="Demo voucher for the ReLoop Hub pilot.",
                required_points=100,
                value_text="5,000 VND discount",
                quantity_available=50,
                status=VoucherStatus.ACTIVE,
            ),
            add_if_missing(
                session,
                Vehicle,
                VEHICLE_ID,
                code="TRUCK-01",
                driver_id=DRIVER_ID,
                capacity_kg=500,
                latitude=10.762622,
                longitude=106.660172,
                active=True,
            ),
        ]

        auth_defaults = {
            STUDENT_ID: (
                "student@reloop.vn",
                "Student@123",
            ),
            ADMIN_ID: (
                "admin@reloop.vn",
                "Admin@123",
            ),
            DRIVER_ID: (
                "driver@reloop.vn",
                "Driver@123",
            ),
        }
        for user_id, (email, password) in auth_defaults.items():
            user = session.get(User, user_id)
            if user is None:
                continue
            if user.email is None:
                user.email = email
            if user.hashed_password is None:
                user.hashed_password = hash_password(password)
            user.is_active = True

    created_count = sum(results)
    skipped_count = len(results) - created_count

    print("Database seed completed.")
    print(f"Created: {created_count}")
    print(f"Skipped: {skipped_count}")


if __name__ == "__main__":
    main()
