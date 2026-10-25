class TenantError(Exception):
    pass


class ValidationError(TenantError):
    pass


class UnauthorizedError(TenantError):
    pass


class ForbiddenError(TenantError):
    pass


class ProfileNotFoundError(TenantError):
    pass


class RelationNotFoundError(TenantError):
    pass


class RelationConflictError(TenantError):
    pass


class InviteCodeNotFoundError(TenantError):
    pass


class AlreadyLinkedError(TenantError):
    reason = "already_linked"

    def __init__(self, current_trainer_user_id: str) -> None:
        super().__init__("client already linked to another trainer")
        self.current_trainer_user_id = current_trainer_user_id
