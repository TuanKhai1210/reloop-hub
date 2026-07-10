from app.core.database import check_database_connection


def main() -> None:
    check_database_connection()
    print("Database connection successful.")


if __name__ == "__main__":
    main()
