from uuid import UUID

from sqlalchemy.orm import Session

from app.models import (
    HubStatus,
    ReturnSession,
    ReturnSessionStatus,
)
from app.repositories import (
    HubRepository,
    ReturnSessionRepository,
    UserRepository,
)
from app.services.errors import (
    ConflictError,
    EntityNotFoundError,
    InvalidStateError,
)


class ReturnService:
    AVAILABLE_HUB_STATUSES = frozenset(
        {
            HubStatus.ACTIVE,
            HubStatus.NEAR_FULL,
        }
    )

    def __init__(self, session: Session) -> None:
        self.session = session
        self.user_repository = UserRepository(session)
        self.hub_repository = HubRepository(session)
        self.return_session_repository = (
            ReturnSessionRepository(session)
        )

    def start_session(
        self,
        *,
        user_id: UUID,
        hub_id: UUID,
    ) -> ReturnSession:
        if self.session.in_transaction():
            return self._start_session(
                user_id=user_id,
                hub_id=hub_id,
            )

        with self.session.begin():
            return self._start_session(
                user_id=user_id,
                hub_id=hub_id,
            )

    def _start_session(
        self,
        *,
        user_id: UUID,
        hub_id: UUID,
    ) -> ReturnSession:
        user = self.user_repository.get_by_id_for_update(user_id)

        if user is None:
            raise EntityNotFoundError("user not found")

        hub = self.hub_repository.get_by_id(hub_id)

        if hub is None:
            raise EntityNotFoundError("hub not found")

        if hub.status not in self.AVAILABLE_HUB_STATUSES:
            raise InvalidStateError(
                "hub is not available for return sessions"
            )

        existing_session = (
            self.return_session_repository
            .get_latest_open_by_user(user_id)
        )

        if existing_session is not None:
            raise ConflictError(
                "user already has an open return session"
            )

        return self.return_session_repository.add(
            ReturnSession(
                user_id=user.id,
                hub_id=hub.id,
                status=ReturnSessionStatus.OPEN,
                total_accepted=0,
                total_rejected=0,
                total_points=0,
                finished_at=None,
            )
        )
