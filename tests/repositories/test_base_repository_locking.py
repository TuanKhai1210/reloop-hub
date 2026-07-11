from unittest.mock import Mock
from uuid import uuid4

from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.models import User
from app.repositories import BaseRepository


def test_get_by_id_for_update_builds_locking_statement() -> None:
    session = Mock(spec=Session)
    session.scalars.return_value.one_or_none.return_value = None

    repository = BaseRepository(session, User)

    result = repository.get_by_id_for_update(uuid4())

    statement = session.scalars.call_args.args[0]
    compiled_statement = str(
        statement.compile(
            dialect=postgresql.dialect()
        )
    )

    assert result is None
    assert compiled_statement.rstrip().endswith("FOR UPDATE")
