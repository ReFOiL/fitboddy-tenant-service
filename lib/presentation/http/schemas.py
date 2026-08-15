from datetime import datetime

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str


class UpsertDiscoveryProfileRequest(BaseModel):
    role: str = Field(min_length=6, max_length=32)
    is_visible: bool = True
    looking_for_trainer: bool = False


class CreateRelationRequest(BaseModel):
    trainer_user_id: str = Field(min_length=1, max_length=64)
    client_user_id: str = Field(min_length=1, max_length=64)
    mode: str = Field(default="invite", min_length=6, max_length=16)


class CompatMembershipCheckRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)
    allowed_roles: list[str] = Field(default_factory=list)


class ProfileAccessCheckRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)
    allowed_roles: list[str] = Field(default_factory=list)


class DiscoveryProfileResponse(BaseModel):
    user_id: str
    display_name: str | None = None
    login: str | None = None
    role: str
    is_visible: bool
    looking_for_trainer: bool
    created_at: datetime
    updated_at: datetime


class TrainerClientRelationResponse(BaseModel):
    relation_id: str
    trainer_user_id: str
    trainer_login: str | None = None
    client_user_id: str
    client_login: str | None = None
    client_display_name: str | None = None
    status: str
    source: str
    created_at: datetime
    updated_at: datetime


class TrainerFunnelResponse(BaseModel):
    trainer_user_id: str
    invites_sent: int
    invites_pending: int
    invites_accepted: int
    invites_declined: int
    active_clients: int
    invite_acceptance_rate: float


class TrainerPublicationStatusResponse(BaseModel):
    trainer_user_id: str
    is_published: bool


class CompatMembershipCheckResponse(BaseModel):
    is_member: bool
    role: str | None = None


class ProfileAccessCheckResponse(BaseModel):
    exists: bool
    role: str | None = None


class AdminSetPublicationRequest(BaseModel):
    is_visible: bool


class AdminProfileListResponse(BaseModel):
    items: list[DiscoveryProfileResponse] = Field(default_factory=list)
    total: int
    page: int
    page_size: int


class AdminRelationListResponse(BaseModel):
    items: list[TrainerClientRelationResponse] = Field(default_factory=list)
    total: int
    page: int
    page_size: int


class AdminStatsResponse(BaseModel):
    trainers: int
    clients: int
    relations_total: int
    relations_active: int
    relations_invited: int
