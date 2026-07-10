from collections.abc import Generator

import pytest
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.core.database import engine


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


@pytest.fixture(scope="session")
def verify_database_schema() -> None:
    existing_tables = set(
        inspect(engine).get_table_names(schema="public")
    )
    missing_tables = REQUIRED_TABLES - existing_tables

    if missing_tables:
        missing_names = ", ".join(sorted(missing_tables))
        pytest.fail(
            "Database schema is incomplete. "
            f"Missing tables: {missing_names}. "
            "Run `python -m alembic upgrade head`."
        )


@pytest.fixture
def db_session(
    verify_database_schema: None,
) -> Generator[Session, None, None]:
    with engine.connect() as connection:
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
