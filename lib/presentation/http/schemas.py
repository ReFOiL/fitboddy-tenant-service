from datetime import datetime

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str


class UpsertDiscoveryProfileRequest(BaseModel):
    role: str = Field(min_length=6, max_length=32)
    is_visible: bool = True
    looking_for_trainer: bool = False


class CreateRelationRequest(BaseModel):
    acting_user_id: str = Field(min_length=1, max_length=64)
    trainer_user_id: str = Field(min_length=1, max_length=64)
    client_user_id: str = Field(min_length=1, max_length=64)
    mode: str = Field(default="invite", min_length=6, max_length=16)


class AcceptRelationRequest(BaseModel):
    acting_user_id: str = Field(min_length=1, max_length=64)


class LeaveRelationRequest(BaseModel):
    acting_user_id: str = Field(min_length=1, max_length=64)


class CompatMembershipCheckRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)
    allowed_roles: list[str] = Field(default_factory=list)


class ProfileAccessCheckRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)
    allowed_roles: list[str] = Field(default_factory=list)


class DiscoveryProfileResponse(BaseModel):
    user_id: str
    role: str
    is_visible: bool
    looking_for_trainer: bool
    created_at: datetime
    updated_at: datetime


class TrainerClientRelationResponse(BaseModel):
    relation_id: str
    trainer_user_id: str
    client_user_id: str
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


class CompatMembershipCheckResponse(BaseModel):
    is_member: bool
    role: str | None = None


class ProfileAccessCheckResponse(BaseModel):
    exists: bool
    role: str | None = None
