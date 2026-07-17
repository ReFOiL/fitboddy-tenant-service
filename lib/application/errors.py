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
