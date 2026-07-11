from collections.abc import Generator

import pytest
from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session


REQUIRED_TABLES = {
    "users",
    "hubs",
    "return_sessions",
    "material_batches",
    "bottle_transactions",
    "point_ledger",
    "vouchers",
    "voucher_redemptions",
    "pickups",
    "verification_events",
}


class TestDatabaseSettings(BaseSettings):
    app_env: str
    test_database_url: str

    model_config = SettingsConfigDict(
        env_file=".env.test",
        env_file_encoding="utf-8-sig",
        case_sensitive=False,
        extra="ignore",
    )


@pytest.fixture(scope="session")
def database_engine() -> Generator[Engine, None, None]:
    try:
        test_settings = TestDatabaseSettings()
    except ValidationError as error:
        pytest.exit(
            "Test database configuration is invalid. "
            "Create .env.test with APP_ENV=test and "
            f"TEST_DATABASE_URL. Details: {error}",
            returncode=2,
        )

    if test_settings.app_env.casefold() != "test":
        pytest.exit(
            "Refusing to run database tests: "
            "APP_ENV must equal test.",
            returncode=2,
        )

    database_url = make_url(
        test_settings.test_database_url
    )
    configured_database = database_url.database

    if (
        configured_database is None
        or not configured_database.endswith("_test")
    ):
        pytest.exit(
            "Refusing to run database tests: "
            "the configured database name must end with _test.",
            returncode=2,
        )

    test_engine = create_engine(
        test_settings.test_database_url,
        pool_pre_ping=True,
        connect_args={
            "connect_timeout": 5,
        },
    )

    try:
        with test_engine.connect() as connection:
            actual_database = connection.scalar(
                text("SELECT current_database()")
            )

        if actual_database != configured_database:
            pytest.exit(
                "Refusing to run database tests: "
                "the connected database does not match "
                "TEST_DATABASE_URL.",
                returncode=2,
            )

        if not actual_database.endswith("_test"):
            pytest.exit(
                "Refusing to run database tests: "
                "the connected database name must end "
                "with _test.",
                returncode=2,
            )

        yield test_engine

    finally:
        test_engine.dispose()


@pytest.fixture(scope="session")
def verify_database_schema(
    database_engine: Engine,
) -> None:
    existing_tables = set(
        inspect(database_engine).get_table_names(
            schema="public"
        )
    )
    missing_tables = REQUIRED_TABLES - existing_tables

    if missing_tables:
        missing_names = ", ".join(
            sorted(missing_tables)
        )
        pytest.fail(
            "Test database schema is incomplete. "
            f"Missing tables: {missing_names}. "
            "Run Alembic migrations against "
            "reloop_hub_test."
        )


@pytest.fixture
def db_session(
    verify_database_schema: None,
    database_engine: Engine,
) -> Generator[Session, None, None]:
    with database_engine.connect() as connection:
        outer_transaction = connection.begin()

        session = Session(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )

        try:
            yield session
        finally:
            session.close()

            if outer_transaction.is_active:
                outer_transaction.rollback()
