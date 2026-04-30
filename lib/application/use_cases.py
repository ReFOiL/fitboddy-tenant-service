from __future__ import annotations

from datetime import datetime, UTC
from uuid import uuid4

from sqlalchemy.orm import Session

from application.commands import (
    AcceptRelationCommand,
    CheckProfileAccessCommand,
    CreateRelationCommand,
    GetClientActiveRelationCommand,
    GetTrainerFunnelCommand,
    LeaveRelationCommand,
    ListIncomingInvitesCommand,
    ListTrainerClientsCommand,
    UpsertDiscoveryProfileCommand,
)
from application.errors import ProfileNotFoundError, RelationNotFoundError, ValidationError
from application.models import DiscoveryProfileModel, TrainerClientRelationModel
from application.repositories import DiscoveryProfileRepository, TrainerClientRelationRepository
from domain.entities import DiscoveryProfile, TrainerClientRelation, TrainerFunnelMetrics


class TenantService:
    _ALLOWED_ROLES = {"trainer", "client"}
    _ALLOWED_RELATION_MODES = {"invite", "direct"}
    _ALLOWED_RELATION_STATUSES = {"invited", "active", "declined", "ended", "left"}

    def __init__(self, session: Session) -> None:
        self._session = session
        self._profiles = DiscoveryProfileRepository(session)
        self._relations = TrainerClientRelationRepository(session)

    def upsert_profile(self, command: UpsertDiscoveryProfileCommand) -> DiscoveryProfile:
        self._ensure_role_supported(command.role)
        now = datetime.now(UTC).replace(tzinfo=None)
        profile = self._profiles.upsert(
            DiscoveryProfileModel(
                user_id=command.user_id,
                role=command.role,
                is_visible=command.is_visible,
                looking_for_trainer=command.looking_for_trainer,
                created_at=now,
                updated_at=now,
            )
        )
        self._session.commit()
        return self._to_domain_profile(profile)

    def list_trainers(self) -> list[DiscoveryProfile]:
        return [self._to_domain_profile(item) for item in self._profiles.list_visible_trainers()]

    def list_clients_looking_for_trainer(self) -> list[DiscoveryProfile]:
        return [self._to_domain_profile(item) for item in self._profiles.list_clients_looking_for_trainer()]

    def create_relation(self, command: CreateRelationCommand) -> TrainerClientRelation:
        self._ensure_relation_mode_supported(command.mode)
        trainer_profile = self._profiles.find_by_id(command.trainer_user_id)
        client_profile = self._profiles.find_by_id(command.client_user_id)
        if trainer_profile is None or trainer_profile.role != "trainer":
            raise ProfileNotFoundError("trainer profile not found")
        if client_profile is None or client_profile.role != "client":
            raise ProfileNotFoundError("client profile not found")
        self._ensure_relation_actor_permissions(command)

        now = datetime.now(UTC).replace(tzinfo=None)
        relation_status = "invited" if command.mode == "invite" else "active"
        if relation_status == "active":
            self._close_existing_active_client_relation(command.client_user_id, now)

        relation = self._relations.find_by_pair(command.trainer_user_id, command.client_user_id)
        if relation is None:
            relation = self._relations.add(
                TrainerClientRelationModel(
                    relation_id=str(uuid4()),
                    trainer_user_id=command.trainer_user_id,
                    client_user_id=command.client_user_id,
                    status=relation_status,
                    source=command.mode,
                    created_at=now,
                    updated_at=now,
                )
            )
        else:
            relation.status = relation_status
            relation.source = command.mode
            relation.updated_at = now
            self._session.flush()

        if relation.status == "active":
            client_profile.looking_for_trainer = False
            client_profile.updated_at = now
            self._session.flush()

        self._session.commit()
        return self._to_domain_relation(relation)

    def list_incoming_invites(self, command: ListIncomingInvitesCommand) -> list[TrainerClientRelation]:
        return [
            self._to_domain_relation(item)
            for item in self._relations.list_incoming_invites(command.client_user_id)
        ]

    def get_client_active_relation(self, command: GetClientActiveRelationCommand) -> TrainerClientRelation:
        relation = self._relations.find_active_by_client(command.client_user_id)
        if relation is None:
            raise RelationNotFoundError("active relation not found for client")
        return self._to_domain_relation(relation)

    def get_trainer_funnel(self, command: GetTrainerFunnelCommand) -> TrainerFunnelMetrics:
        invites_pending = self._relations.count_by_trainer_statuses(
            command.trainer_user_id,
            statuses=["invited"],
            source="invite",
        )
        invites_declined = self._relations.count_by_trainer_statuses(
            command.trainer_user_id,
            statuses=["declined"],
            source="invite",
        )
        invites_accepted = self._relations.count_by_trainer_statuses(
            command.trainer_user_id,
            statuses=["active", "ended", "left"],
            source="invite",
        )
        invites_sent = invites_pending + invites_declined + invites_accepted
        active_clients = self._relations.count_by_trainer_statuses(
            command.trainer_user_id,
            statuses=["active"],
        )
        invite_acceptance_rate = round((invites_accepted / invites_sent) * 100, 1) if invites_sent > 0 else 0.0
        return TrainerFunnelMetrics(
            trainer_user_id=command.trainer_user_id,
            invites_sent=invites_sent,
            invites_pending=invites_pending,
            invites_accepted=invites_accepted,
            invites_declined=invites_declined,
            active_clients=active_clients,
            invite_acceptance_rate=invite_acceptance_rate,
        )

    def accept_relation(self, command: AcceptRelationCommand) -> TrainerClientRelation:
        relation = self._relations.find_by_id(command.relation_id)
        if relation is None:
            raise RelationNotFoundError("relation not found")
        if relation.status != "invited":
            raise ValidationError("only invited relation can be accepted")
        self._ensure_actor_is_relation_participant(command.acting_user_id, relation)

        now = datetime.now(UTC).replace(tzinfo=None)
        self._close_existing_active_client_relation(relation.client_user_id, now)
        relation.status = "active"
        relation.updated_at = now
        client_profile = self._profiles.find_by_id(relation.client_user_id)
        if client_profile is not None and client_profile.role == "client":
            client_profile.looking_for_trainer = False
            client_profile.updated_at = now
            self._session.flush()
        self._session.commit()
        return self._to_domain_relation(relation)

    def leave_relation(self, command: LeaveRelationCommand) -> TrainerClientRelation:
        relation = self._relations.find_by_id(command.relation_id)
        if relation is None:
            raise RelationNotFoundError("relation not found")
        if relation.status in {"declined", "ended", "left"}:
            raise ValidationError("relation already closed")
        self._ensure_actor_is_relation_participant(command.acting_user_id, relation)
        relation.status = "declined" if relation.status == "invited" else "ended"
        relation.updated_at = datetime.now(UTC).replace(tzinfo=None)
        self._session.commit()
        return self._to_domain_relation(relation)

    def list_trainer_clients(self, command: ListTrainerClientsCommand) -> list[TrainerClientRelation]:
        if command.status not in self._ALLOWED_RELATION_STATUSES:
            raise ValidationError("unsupported relation status")
        if command.status == "ended":
            return [
                self._to_domain_relation(item)
                for item in self._relations.list_by_trainer_statuses(command.trainer_user_id, ["ended", "left"])
            ]
        if command.status == "left":
            return []
        return [
            self._to_domain_relation(item)
            for item in self._relations.list_by_trainer(command.trainer_user_id, command.status)
        ]

    def check_profile_access(self, command: CheckProfileAccessCommand) -> DiscoveryProfile | None:
        profile = self._profiles.find_by_id(command.user_id)
        if profile is None:
            return None
        if command.allowed_roles and profile.role not in command.allowed_roles:
            return None
        return self._to_domain_profile(profile)

    def _close_existing_active_client_relation(self, client_user_id: str, now: datetime) -> None:
        existing_active = self._relations.find_active_by_client(client_user_id)
        if existing_active is None:
            return
        existing_active.status = "ended"
        existing_active.updated_at = now

    def _ensure_role_supported(self, role: str) -> None:
        if role not in self._ALLOWED_ROLES:
            raise ValidationError("unsupported role")

    def _ensure_relation_mode_supported(self, mode: str) -> None:
        if mode not in self._ALLOWED_RELATION_MODES:
            raise ValidationError("unsupported relation mode")

    @staticmethod
    def _ensure_actor_is_relation_participant(actor_user_id: str, relation: TrainerClientRelationModel) -> None:
        if actor_user_id not in {relation.trainer_user_id, relation.client_user_id}:
            raise ValidationError("actor is not relation participant")

    @staticmethod
    def _ensure_relation_actor_permissions(command: CreateRelationCommand) -> None:
        if command.acting_user_id not in {command.trainer_user_id, command.client_user_id}:
            raise ValidationError("actor is not relation participant")
        if command.mode == "invite" and command.acting_user_id != command.trainer_user_id:
            raise ValidationError("only trainer can send invite")

    @staticmethod
    def _to_domain_profile(model: DiscoveryProfileModel) -> DiscoveryProfile:
        return DiscoveryProfile(
            user_id=model.user_id,
            role=model.role,
            is_visible=model.is_visible,
            looking_for_trainer=model.looking_for_trainer,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def _to_domain_relation(model: TrainerClientRelationModel) -> TrainerClientRelation:
        return TrainerClientRelation(
            relation_id=model.relation_id,
            trainer_user_id=model.trainer_user_id,
            client_user_id=model.client_user_id,
            status=model.status,
            source=model.source,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
