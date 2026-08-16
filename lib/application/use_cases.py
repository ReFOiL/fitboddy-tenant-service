from __future__ import annotations

from datetime import datetime, UTC
from uuid import uuid4

from sqlalchemy.orm import Session

from application.commands import (
    AcceptRelationCommand,
    CheckProfileAccessCommand,
    CheckRelationAccessCommand,
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
from application.errors import ForbiddenError, ProfileNotFoundError, RelationNotFoundError, ValidationError
from application.gateways import AuthGateway, ProfileGateway
from application.models import DiscoveryProfileModel, TrainerClientRelationModel
from application.repositories import DiscoveryProfileRepository, TrainerClientRelationRepository
from domain.entities import DiscoveryProfile, RelationAccess, TrainerClientRelation, TrainerFunnelMetrics


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
        offset, limit = self._pagination_window(command.page, command.page_size)
        if search is None:
            if limit is None:
                profiles = self._profiles.list_visible_trainers()
                total = len(profiles)
            else:
                profiles = self._profiles.list_visible_trainers(offset=offset, limit=limit)
                total = self._profiles.count_visible_trainers()
            page_user_ids = [profile.user_id for profile in profiles]
            names_map = self._resolve_names(page_user_ids)
            logins_map = self._resolve_logins(page_user_ids)
            return [
                self._to_domain_profile(
                    item,
                    display_name=names_map.get(item.user_id),
                    login=logins_map.get(item.user_id),
                )
                for item in profiles
            ], total

        trainer_ids = self._profiles.list_visible_trainer_ids()
        names_map = self._resolve_names(trainer_ids)
        matched_ids = self._filter_ids_by_name(trainer_ids, names_map, search)
        paged_ids = self._paginate_collection(matched_ids, command.page, command.page_size)
        profiles = self._profiles.list_by_user_ids(paged_ids)
        logins_map = self._resolve_logins(paged_ids)
        return [
            self._to_domain_profile(
                item,
                display_name=names_map.get(item.user_id),
                login=logins_map.get(item.user_id),
            )
            for item in profiles
        ], len(matched_ids)

    def create_relation(self, command: CreateRelationCommand) -> TrainerClientRelation:
        self._ensure_relation_mode_supported(command.mode)
        now = datetime.now(UTC).replace(tzinfo=None)
        trainer_profile = self._profiles.find_by_id(command.trainer_user_id)
        client_profile = self._profiles.find_by_id(command.client_user_id)
        if trainer_profile is None or trainer_profile.role != "trainer":
            raise ProfileNotFoundError("trainer profile not found")
        if client_profile is None:
            can_autocreate_client_profile = command.mode == "direct" and command.acting_user_id == command.client_user_id
            if can_autocreate_client_profile:
                client_profile = self._profiles.upsert(
                    DiscoveryProfileModel(
                        user_id=command.client_user_id,
                        role="client",
                        is_visible=False,
                        looking_for_trainer=False,
                        created_at=now,
                        updated_at=now,
                    )
                )
            else:
                raise ProfileNotFoundError("client profile not found")
        elif client_profile.role != "client":
            raise ProfileNotFoundError("client profile not found")
        self._ensure_relation_actor_permissions(command)
        relation_status = "invited" if command.mode == "invite" else "active"
        if relation_status == "active":
            existing_active = self._relations.find_active_by_client(command.client_user_id)
            if existing_active is not None:
                if existing_active.trainer_user_id == command.trainer_user_id:
                    raise ValidationError("client already connected to this trainer")
                raise ValidationError("client already has active relation")

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
        if command.acting_user_id != relation.client_user_id:
            raise ForbiddenError("only invited client can accept relation")

        now = datetime.now(UTC).replace(tzinfo=None)
        self._close_existing_active_client_relation(relation.client_user_id, now)
        relation.status = "active"
        relation.updated_at = now
        client_profile = self._profiles.find_by_id(relation.client_user_id)
        if client_profile is not None and client_profile.role == "client":
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
        offset, limit = self._pagination_window(command.page, command.page_size)
        if search is None:
            if limit is None:
                relations = self._relations.list_by_trainer_statuses(command.trainer_user_id, statuses)
                total = len(relations)
            else:
                relations = self._relations.list_by_trainer_statuses(
                    command.trainer_user_id,
                    statuses,
                    offset=offset,
                    limit=limit,
                )
                total = self._relations.count_by_trainer_statuses(command.trainer_user_id, statuses)
            page_client_ids = [relation.client_user_id for relation in relations]
            names_map = self._resolve_names(page_client_ids)
            logins_map = self._resolve_logins(
                list({user_id for relation in relations for user_id in (relation.trainer_user_id, relation.client_user_id)})
            )
            return [
                self._to_domain_relation(
                    item,
                    client_display_name=names_map.get(item.client_user_id),
                    trainer_login=logins_map.get(item.trainer_user_id),
                    client_login=logins_map.get(item.client_user_id),
                )
                for item in relations
            ], total

        id_pairs = self._relations.list_ids_by_trainer_statuses(command.trainer_user_id, statuses)
        client_ids = [client_user_id for _, client_user_id in id_pairs]
        names_map = self._resolve_names(client_ids)
        matched_ids = [
            relation_id
            for relation_id, client_user_id in id_pairs
            if search.lower() in names_map.get(client_user_id, "").lower() or search.lower() in client_user_id.lower()
        ]
        paged_ids = self._paginate_collection(matched_ids, command.page, command.page_size)
        relations = self._relations.list_by_ids(paged_ids)
        logins_map = self._resolve_logins(
            list({user_id for relation in relations for user_id in (relation.trainer_user_id, relation.client_user_id)})
        )
        return [
            self._to_domain_relation(
                item,
                client_display_name=names_map.get(item.client_user_id),
                trainer_login=logins_map.get(item.trainer_user_id),
                client_login=logins_map.get(item.client_user_id),
            )
            for item in relations
        ], len(matched_ids)

    def admin_list_profiles(
        self,
        *,
        role: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[DiscoveryProfile], int]:
        page = max(page, 1)
        page_size = min(max(page_size, 1), 100)
        offset = (page - 1) * page_size
        if role:
            self._ensure_role_supported(role)
        rows, total = self._profiles.list_all(role=role, offset=offset, limit=page_size)
        names_map = self._resolve_names([row.user_id for row in rows])
        logins_map = self._resolve_logins([row.user_id for row in rows])
        return [
            self._to_domain_profile(
                row,
                display_name=names_map.get(row.user_id),
                login=logins_map.get(row.user_id),
            )
            for row in rows
        ], total

    def admin_set_publication(self, user_id: str, is_visible: bool) -> DiscoveryProfile:
        profile = self._profiles.find_by_id(user_id)
        if profile is None:
            raise ProfileNotFoundError("profile not found")
        profile.is_visible = is_visible
        profile.updated_at = datetime.now(UTC).replace(tzinfo=None)
        self._session.commit()
        names_map = self._resolve_names([user_id])
        logins_map = self._resolve_logins([user_id])
        return self._to_domain_profile(
            profile,
            display_name=names_map.get(user_id),
            login=logins_map.get(user_id),
        )

    def admin_list_relations(
        self,
        *,
        status: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[TrainerClientRelation], int]:
        page = max(page, 1)
        page_size = min(max(page_size, 1), 100)
        offset = (page - 1) * page_size
        if status and status not in self._ALLOWED_RELATION_STATUSES:
            raise ValidationError("unsupported relation status")
        rows, total = self._relations.list_all(status=status, offset=offset, limit=page_size)
        user_ids = list(
            {user_id for row in rows for user_id in (row.trainer_user_id, row.client_user_id)}
        )
        names_map = self._resolve_names([row.client_user_id for row in rows])
        logins_map = self._resolve_logins(user_ids)
        return [
            self._to_domain_relation(
                row,
                client_display_name=names_map.get(row.client_user_id),
                trainer_login=logins_map.get(row.trainer_user_id),
                client_login=logins_map.get(row.client_user_id),
            )
            for row in rows
        ], total

    def admin_force_leave_relation(self, relation_id: str) -> TrainerClientRelation:
        relation = self._relations.find_by_id(relation_id)
        if relation is None:
            raise RelationNotFoundError("relation not found")
        if relation.status in {"declined", "ended", "left"}:
            raise ValidationError("relation already closed")
        relation.status = "declined" if relation.status == "invited" else "ended"
        relation.updated_at = datetime.now(UTC).replace(tzinfo=None)
        self._session.commit()
        relation_logins = self._resolve_logins([relation.trainer_user_id, relation.client_user_id])
        return self._to_domain_relation(
            relation,
            trainer_login=relation_logins.get(relation.trainer_user_id),
            client_login=relation_logins.get(relation.client_user_id),
        )

    def admin_stats(self) -> dict[str, int]:
        return {
            "trainers": self._profiles.count_by_role("trainer"),
            "clients": self._profiles.count_by_role("client"),
            "relations_total": self._relations.count_all(),
            "relations_active": self._relations.count_by_status("active"),
            "relations_invited": self._relations.count_by_status("invited"),
        }

    def check_profile_access(self, command: CheckProfileAccessCommand) -> DiscoveryProfile | None:
        profile = self._profiles.find_by_id(command.user_id)
        if profile is None:
            return None
        if command.allowed_roles and profile.role not in command.allowed_roles:
            return None
        return self._to_domain_profile(profile)

    def check_relation_access(self, command: CheckRelationAccessCommand) -> RelationAccess:
        relation = self._relations.find_by_pair(command.trainer_user_id, command.client_user_id)
        if relation is None:
            return RelationAccess(allowed=False, relation_id=None, status=None)
        return RelationAccess(
            allowed=relation.status == "active",
            relation_id=relation.relation_id,
            status=relation.status,
        )

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
    def _pagination_window(page: int | None, page_size: int | None) -> tuple[int, int | None]:
        if page is None and page_size is None:
            return 0, None
        if page is None or page_size is None:
            raise ValidationError("page and page_size should be passed together")
        return (page - 1) * page_size, page_size

    @staticmethod
    def _filter_ids_by_name(user_ids: list[str], names_map: dict[str, str], search: str) -> list[str]:
        lowered = search.lower()
        return [
            user_id
            for user_id in user_ids
            if lowered in names_map.get(user_id, "").lower() or lowered in user_id.lower()
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
            raise ForbiddenError("actor is not relation participant")

    @staticmethod
    def _ensure_relation_actor_permissions(command: CreateRelationCommand) -> None:
        if command.acting_user_id not in {command.trainer_user_id, command.client_user_id}:
            raise ForbiddenError("actor is not relation participant")
        if command.mode == "invite" and command.acting_user_id != command.trainer_user_id:
            raise ForbiddenError("only trainer can send invite")

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
