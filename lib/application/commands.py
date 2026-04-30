from dataclasses import dataclass


@dataclass(frozen=True)
class UpsertDiscoveryProfileCommand:
    user_id: str
    role: str
    is_visible: bool
    looking_for_trainer: bool


@dataclass(frozen=True)
class CreateRelationCommand:
    acting_user_id: str
    trainer_user_id: str
    client_user_id: str
    mode: str


@dataclass(frozen=True)
class AcceptRelationCommand:
    relation_id: str
    acting_user_id: str


@dataclass(frozen=True)
class LeaveRelationCommand:
    relation_id: str
    acting_user_id: str


@dataclass(frozen=True)
class ListTrainerClientsCommand:
    trainer_user_id: str
    status: str


@dataclass(frozen=True)
class ListIncomingInvitesCommand:
    client_user_id: str


@dataclass(frozen=True)
class GetClientActiveRelationCommand:
    client_user_id: str


@dataclass(frozen=True)
class GetTrainerFunnelCommand:
    trainer_user_id: str


@dataclass(frozen=True)
class CheckProfileAccessCommand:
    user_id: str
    allowed_roles: list[str]
