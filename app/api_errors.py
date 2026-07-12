from fastapi import HTTPException

from app.services import (
    ConflictError,
    EntityNotFoundError,
    InvalidStateError,
)


def service_http_error(error: Exception) -> HTTPException:
    if isinstance(error, EntityNotFoundError):
        return HTTPException(status_code=404, detail=str(error))
    if isinstance(error, (ConflictError, InvalidStateError)):
        return HTTPException(status_code=409, detail=str(error))
    return HTTPException(status_code=500, detail="Internal service error")
