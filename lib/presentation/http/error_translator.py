from fastapi import HTTPException, status

from application.errors import (
    ProfileNotFoundError,
    RelationConflictError,
    RelationNotFoundError,
    TenantError,
    ValidationError,
)


class ErrorTranslator:
    @staticmethod
    def raise_http_error(exc: TenantError) -> None:
        if isinstance(exc, RelationConflictError):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        if isinstance(exc, ProfileNotFoundError):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        if isinstance(exc, RelationNotFoundError):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        if isinstance(exc, ValidationError):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
