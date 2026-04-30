class TenantError(Exception):
    pass


class ValidationError(TenantError):
    pass


class ProfileNotFoundError(TenantError):
    pass


class RelationNotFoundError(TenantError):
    pass


class RelationConflictError(TenantError):
    pass
