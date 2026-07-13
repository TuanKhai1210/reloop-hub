"""Apply Alembic migrations to the isolated database in .env.test."""

import os
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy.engine import make_url


def main() -> None:
    env_path = Path(".env.test")
    if not env_path.is_file():
        raise SystemExit(
            "Missing .env.test. Copy .env.test.example and set "
            "TEST_DATABASE_URL first."
        )
    values = dotenv_values(env_path)
    database_url = values.get("TEST_DATABASE_URL")
    app_env = (values.get("APP_ENV") or "").casefold()
    if not database_url:
        raise SystemExit("TEST_DATABASE_URL is missing from .env.test.")
    if app_env != "test":
        raise SystemExit("APP_ENV in .env.test must equal test.")
    parsed_url = make_url(database_url)
    if not parsed_url.database or not parsed_url.database.endswith("_test"):
        raise SystemExit(
            "Refusing to migrate: test database name must end with _test."
        )

    os.environ["APP_ENV"] = "test"
    os.environ["DATABASE_URL"] = database_url

    from alembic import command
    from alembic.config import Config

    command.upgrade(Config("alembic.ini"), "head")
    print(
        "Test database migrated to Alembic head: "
        f"{parsed_url.database}"
    )


if __name__ == "__main__":
    main()
