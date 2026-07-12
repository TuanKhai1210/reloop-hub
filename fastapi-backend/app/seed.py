from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.models import Hub, HubStatus, User, UserRole, Vehicle
from app.security import hash_password


def seed() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if not db.scalar(select(User).where(User.email == "admin@reloop.vn")):
            db.add_all(
                [
                    User(
                        email="admin@reloop.vn",
                        full_name="ReLoop Admin",
                        hashed_password=hash_password("Admin@123"),
                        role=UserRole.ADMIN,
                    ),
                    User(
                        email="student@reloop.vn",
                        full_name="Nguyễn Minh Anh",
                        hashed_password=hash_password("Student@123"),
                        role=UserRole.RESIDENT,
                    ),
                ]
            )
        if not db.scalar(select(Hub).limit(1)):
            db.add_all(
                [
                    Hub(code="HUB-UEH-01", name="UEH Nguyễn Văn Linh", address="Nguyễn Văn Linh, Quận 7, TP.HCM", latitude=10.7298, longitude=106.6957, capacity_kg=200, current_load_kg=164, fill_level=82, status=HubStatus.ONLINE, camera_online=True, sensor_online=True),
                    Hub(code="HUB-IUH-01", name="Đại học Công nghiệp", address="12 Nguyễn Văn Bảo, Gò Vấp, TP.HCM", latitude=10.8222, longitude=106.6872, capacity_kg=200, current_load_kg=190, fill_level=95, status=HubStatus.FULL, camera_online=True, sensor_online=True),
                    Hub(code="HUB-HCMUT-01", name="Đại học Bách Khoa", address="268 Lý Thường Kiệt, Quận 10, TP.HCM", latitude=10.7721, longitude=106.6579, capacity_kg=200, current_load_kg=144, fill_level=72, status=HubStatus.ONLINE, camera_online=True, sensor_online=True),
                    Hub(code="HUB-VNU-01", name="ĐHQG TP.HCM", address="Linh Trung, Thủ Đức, TP.HCM", latitude=10.8700, longitude=106.8031, capacity_kg=200, current_load_kg=80, fill_level=40, status=HubStatus.ONLINE, camera_online=True, sensor_online=True),
                ]
            )
        if not db.scalar(select(Vehicle).limit(1)):
            db.add(Vehicle(code="TRUCK-01", capacity_kg=600, latitude=10.7769, longitude=106.7009))
        db.commit()
        print("Seed completed")
        print("Admin: admin@reloop.vn / Admin@123")
        print("Resident: student@reloop.vn / Student@123")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
