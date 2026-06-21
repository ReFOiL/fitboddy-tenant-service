from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class DiscoveryProfile:
    user_id: str
    display_name: str | None
    role: str
    is_visible: bool
    looking_for_trainer: bool
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class TrainerClientRelation:
    relation_id: str
    trainer_user_id: str
    client_user_id: str
    client_display_name: str | None
    status: str
    source: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class TrainerFunnelMetrics:
    trainer_user_id: str
    invites_sent: int
    invites_pending: int
    invites_accepted: int
    invites_declined: int
    active_clients: int
    invite_acceptance_rate: float
