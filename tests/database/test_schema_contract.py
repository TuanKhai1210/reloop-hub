import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

import app.models
from app.models.base import Base


pytestmark = pytest.mark.integration


MODEL_TABLE_NAMES = sorted(Base.metadata.tables)


def get_expected_foreign_keys(
    table_name: str,
) -> set[tuple[str, str, str]]:
    table = Base.metadata.tables[table_name]

    return {
        (
            foreign_key.parent.name,
            foreign_key.column.table.name,
            foreign_key.column.name,
        )
        for foreign_key in table.foreign_keys
    }


def get_actual_foreign_keys(
    table_name: str,
    database_engine: Engine,
) -> set[tuple[str, str, str]]:
    database_inspector = inspect(database_engine)
    foreign_keys = database_inspector.get_foreign_keys(
        table_name,
        schema="public",
    )

    result: set[tuple[str, str, str]] = set()

    for foreign_key in foreign_keys:
        referred_table = foreign_key["referred_table"]

        for local_column, referred_column in zip(
            foreign_key["constrained_columns"],
            foreign_key["referred_columns"],
            strict=True,
        ):
            result.add(
                (
                    local_column,
                    referred_table,
                    referred_column,
                )
            )

    return result


def test_database_tables_match_model_metadata(
    database_engine: Engine,
) -> None:
    database_inspector = inspect(database_engine)

    actual_tables = set(
        database_inspector.get_table_names(
            schema="public"
        )
    )

    actual_application_tables = (
        actual_tables - {"alembic_version"}
    )
    expected_application_tables = set(
        MODEL_TABLE_NAMES
    )

    assert actual_application_tables == (
        expected_application_tables
    )


@pytest.mark.parametrize(
    "table_name",
    MODEL_TABLE_NAMES,
)
def test_database_columns_match_model_metadata(
    table_name: str,
    database_engine: Engine,
) -> None:
    database_inspector = inspect(database_engine)
    model_table = Base.metadata.tables[table_name]

    expected_columns = {
        column.name
        for column in model_table.columns
    }

    actual_columns = {
        column["name"]
        for column in database_inspector.get_columns(
            table_name,
            schema="public",
        )
    }

    assert actual_columns == expected_columns


@pytest.mark.parametrize(
    "table_name",
    MODEL_TABLE_NAMES,
)
def test_database_primary_key_matches_model_metadata(
    table_name: str,
    database_engine: Engine,
) -> None:
    database_inspector = inspect(database_engine)
    model_table = Base.metadata.tables[table_name]

    expected_primary_key = {
        column.name
        for column in model_table.primary_key.columns
    }

    primary_key_info = (
        database_inspector.get_pk_constraint(
            table_name,
            schema="public",
        )
    )

    actual_primary_key = set(
        primary_key_info["constrained_columns"]
    )

    assert actual_primary_key == expected_primary_key


@pytest.mark.parametrize(
    "table_name",
    MODEL_TABLE_NAMES,
)
def test_database_foreign_keys_match_model_metadata(
    table_name: str,
    database_engine: Engine,
) -> None:
    expected_foreign_keys = get_expected_foreign_keys(
        table_name
    )
    actual_foreign_keys = get_actual_foreign_keys(
        table_name,
        database_engine,
    )

    assert actual_foreign_keys == expected_foreign_keys


def test_database_revision_matches_alembic_head(
    database_engine: Engine,
) -> None:
    alembic_config = Config("alembic.ini")
    script_directory = ScriptDirectory.from_config(
        alembic_config
    )

    migration_heads = set(script_directory.get_heads())

    with database_engine.connect() as connection:
        database_heads = set(
            connection.execute(
                text(
                    "SELECT version_num "
                    "FROM alembic_version"
                )
            ).scalars()
        )

    assert len(migration_heads) == 1
    assert database_heads == migration_heads


def test_database_has_no_schema_drift(
    database_engine: Engine,
) -> None:
    with database_engine.connect() as connection:
        migration_context = MigrationContext.configure(
            connection
        )

        schema_changes = compare_metadata(
            migration_context,
            Base.metadata,
        )

    assert schema_changes == []


def test_return_sessions_has_unique_open_user_index(
    database_engine: Engine,
) -> None:
    database_inspector = inspect(database_engine)
    indexes = database_inspector.get_indexes(
        "return_sessions",
        schema="public",
    )

    target_index = next(
        (
            index
            for index in indexes
            if index["name"]
            == "uq_return_sessions_user_open"
        ),
        None,
    )

    assert target_index is not None
    assert target_index["unique"] is True
    assert target_index["column_names"] == ["user_id"]

    predicate = str(
        target_index["dialect_options"][
            "postgresql_where"
        ]
    )

    assert "status" in predicate
    assert "OPEN" in predicate
