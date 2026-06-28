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
    GetTrainerPublicationStatusCommand,
    LeaveRelationCommand,
    ListDiscoveryProfilesCommand,
    ListIncomingInvitesCommand,
    ListTrainerClientsCommand,
    UpsertDiscoveryProfileCommand,
)
from application.errors import ProfileNotFoundError, RelationNotFoundError, ValidationError
from application.gateways import AuthGateway, ProfileGateway
from application.models import DiscoveryProfileModel, TrainerClientRelationModel
from application.repositories import DiscoveryProfileRepository, TrainerClientRelationRepository
from domain.entities import DiscoveryProfile, TrainerClientRelation, TrainerFunnelMetrics


class TenantService:
    _ALLOWED_ROLES = {"trainer", "client"}
    _ALLOWED_RELATION_MODES = {"invite", "direct"}
    _ALLOWED_RELATION_STATUSES = {"invited", "active", "declined", "ended", "left"}

    def __init__(
        self,
        session: Session,
        profile_gateway: ProfileGateway | None = None,
        auth_gateway: AuthGateway | None = None,
    ) -> None:
        self._session = session
        self._profiles = DiscoveryProfileRepository(session)
        self._relations = TrainerClientRelationRepository(session)
        self._profile_gateway = profile_gateway
        self._auth_gateway = auth_gateway

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

    def list_trainers(self, command: ListDiscoveryProfilesCommand) -> tuple[list[DiscoveryProfile], int]:
        search = self._normalize_search(command.search)
        profiles = self._profiles.list_visible_trainers()
        profile_user_ids = [profile.user_id for profile in profiles]
        names_map = self._resolve_names(profile_user_ids)
        logins_map = self._resolve_logins(profile_user_ids)
        filtered = self._filter_profiles_by_name(profiles, names_map, search)
        paged_profiles = self._paginate_collection(filtered, command.page, command.page_size)
        return [
            self._to_domain_profile(
                item,
                display_name=names_map.get(item.user_id),
                login=logins_map.get(item.user_id),
            )
            for item in paged_profiles
        ], len(filtered)

    def list_clients_looking_for_trainer(
        self,
        command: ListDiscoveryProfilesCommand,
    ) -> tuple[list[DiscoveryProfile], int]:
        search = self._normalize_search(command.search)
        profiles = self._profiles.list_clients_looking_for_trainer()
        profile_user_ids = [profile.user_id for profile in profiles]
        names_map = self._resolve_names(profile_user_ids)
        logins_map = self._resolve_logins(profile_user_ids)
        filtered = self._filter_profiles_by_name(profiles, names_map, search)
        paged_profiles = self._paginate_collection(filtered, command.page, command.page_size)
        return [
            self._to_domain_profile(
                item,
                display_name=names_map.get(item.user_id),
                login=logins_map.get(item.user_id),
            )
            for item in paged_profiles
        ], len(filtered)

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
        relation_logins = self._resolve_logins([relation.trainer_user_id, relation.client_user_id])
        return self._to_domain_relation(
            relation,
            trainer_login=relation_logins.get(relation.trainer_user_id),
            client_login=relation_logins.get(relation.client_user_id),
        )

    def list_incoming_invites(self, command: ListIncomingInvitesCommand) -> list[TrainerClientRelation]:
        relations = self._relations.list_incoming_invites(command.client_user_id)
        relation_user_ids = list(
            {
                user_id
                for relation in relations
                for user_id in (relation.trainer_user_id, relation.client_user_id)
            }
        )
        logins_map = self._resolve_logins(relation_user_ids)
        return [
            self._to_domain_relation(
                item,
                trainer_login=logins_map.get(item.trainer_user_id),
                client_login=logins_map.get(item.client_user_id),
            )
            for item in relations
        ]

    def get_client_active_relation(self, command: GetClientActiveRelationCommand) -> TrainerClientRelation:
        relation = self._relations.find_active_by_client(command.client_user_id)
        if relation is None:
            raise RelationNotFoundError("active relation not found for client")
        relation_logins = self._resolve_logins([relation.trainer_user_id, relation.client_user_id])
        return self._to_domain_relation(
            relation,
            trainer_login=relation_logins.get(relation.trainer_user_id),
            client_login=relation_logins.get(relation.client_user_id),
        )

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

    def get_trainer_publication_status(self, command: GetTrainerPublicationStatusCommand) -> bool:
        profile = self._profiles.find_by_id(command.trainer_user_id)
        if profile is None:
            return False
        return profile.role == "trainer" and profile.is_visible

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
        relation_logins = self._resolve_logins([relation.trainer_user_id, relation.client_user_id])
        return self._to_domain_relation(
            relation,
            trainer_login=relation_logins.get(relation.trainer_user_id),
            client_login=relation_logins.get(relation.client_user_id),
        )

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
        relation_logins = self._resolve_logins([relation.trainer_user_id, relation.client_user_id])
        return self._to_domain_relation(
            relation,
            trainer_login=relation_logins.get(relation.trainer_user_id),
            client_login=relation_logins.get(relation.client_user_id),
        )

    def list_trainer_clients(self, command: ListTrainerClientsCommand) -> tuple[list[TrainerClientRelation], int]:
        if command.status not in self._ALLOWED_RELATION_STATUSES:
            raise ValidationError("unsupported relation status")
        if command.status == "left":
            return [], 0

        statuses = ["ended", "left"] if command.status == "ended" else [command.status]
        search = self._normalize_search(command.search)
        relations = self._relations.list_by_trainer_statuses(
            command.trainer_user_id,
            statuses,
        )
        names_map = self._resolve_names([relation.client_user_id for relation in relations])
        relation_user_ids = list(
            {
                user_id
                for relation in relations
                for user_id in (relation.trainer_user_id, relation.client_user_id)
            }
        )
        logins_map = self._resolve_logins(relation_user_ids)
        filtered_relations = self._filter_relations_by_name(relations, names_map, search)
        paged_relations = self._paginate_collection(filtered_relations, command.page, command.page_size)
        return [
            self._to_domain_relation(
                item,
                client_display_name=names_map.get(item.client_user_id),
                trainer_login=logins_map.get(item.trainer_user_id),
                client_login=logins_map.get(item.client_user_id),
            )
            for item in paged_relations
        ], len(filtered_relations)

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
    def _normalize_search(search: str | None) -> str | None:
        if search is None:
            return None
        normalized = search.strip()
        return normalized or None

    def _resolve_names(self, user_ids: list[str]) -> dict[str, str]:
        if self._profile_gateway is None:
            return {}
        return self._profile_gateway.get_full_names_by_user_ids(user_ids)

    def _resolve_logins(self, user_ids: list[str]) -> dict[str, str]:
        if self._auth_gateway is None:
            return {}
        return self._auth_gateway.get_logins_by_user_ids(user_ids)

    @staticmethod
    def _filter_profiles_by_name(
        profiles: list[DiscoveryProfileModel],
        names_map: dict[str, str],
        search: str | None,
    ) -> list[DiscoveryProfileModel]:
        if search is None:
            return profiles
        lowered = search.lower()
        return [
            profile
            for profile in profiles
            if lowered in names_map.get(profile.user_id, "").lower() or lowered in profile.user_id.lower()
        ]

    @staticmethod
    def _filter_relations_by_name(
        relations: list[TrainerClientRelationModel],
        names_map: dict[str, str],
        search: str | None,
    ) -> list[TrainerClientRelationModel]:
        if search is None:
            return relations
        lowered = search.lower()
        return [
            relation
            for relation in relations
            if lowered in names_map.get(relation.client_user_id, "").lower() or lowered in relation.client_user_id.lower()
        ]

    @staticmethod
    def _paginate_collection[T](items: list[T], page: int | None, page_size: int | None) -> list[T]:
        if page is None and page_size is None:
            return items
        if page is None or page_size is None:
            raise ValidationError("page and page_size should be passed together")
        offset = (page - 1) * page_size
        return items[offset : offset + page_size]

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
    def _to_domain_profile(
        model: DiscoveryProfileModel,
        display_name: str | None = None,
        login: str | None = None,
    ) -> DiscoveryProfile:
        return DiscoveryProfile(
            user_id=model.user_id,
            display_name=display_name,
            login=login,
            role=model.role,
            is_visible=model.is_visible,
            looking_for_trainer=model.looking_for_trainer,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def _to_domain_relation(
        model: TrainerClientRelationModel,
        client_display_name: str | None = None,
        trainer_login: str | None = None,
        client_login: str | None = None,
    ) -> TrainerClientRelation:
        return TrainerClientRelation(
            relation_id=model.relation_id,
            trainer_user_id=model.trainer_user_id,
            trainer_login=trainer_login,
            client_user_id=model.client_user_id,
            client_login=client_login,
            client_display_name=client_display_name,
            status=model.status,
            source=model.source,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
