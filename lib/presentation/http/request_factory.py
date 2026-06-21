from application.commands import (
    AcceptRelationCommand,
    CheckProfileAccessCommand,
    CreateRelationCommand,
    GetClientActiveRelationCommand,
    GetTrainerFunnelCommand,
    LeaveRelationCommand,
    ListDiscoveryProfilesCommand,
    ListIncomingInvitesCommand,
    ListTrainerClientsCommand,
    UpsertDiscoveryProfileCommand,
)
from presentation.http.schemas import (
    AcceptRelationRequest,
    CompatMembershipCheckRequest,
    CreateRelationRequest,
    LeaveRelationRequest,
    ProfileAccessCheckRequest,
    UpsertDiscoveryProfileRequest,
)


class TenantRequestFactory:
    @staticmethod
    def to_upsert_profile_command(user_id: str, payload: UpsertDiscoveryProfileRequest) -> UpsertDiscoveryProfileCommand:
        return UpsertDiscoveryProfileCommand(
            user_id=user_id,
            role=payload.role,
            is_visible=payload.is_visible,
            looking_for_trainer=payload.looking_for_trainer,
        )

    @staticmethod
    def to_create_relation_command(payload: CreateRelationRequest) -> CreateRelationCommand:
        return CreateRelationCommand(
            acting_user_id=payload.acting_user_id,
            trainer_user_id=payload.trainer_user_id,
            client_user_id=payload.client_user_id,
            mode=payload.mode,
        )

    @staticmethod
    def to_accept_relation_command(relation_id: str, payload: AcceptRelationRequest) -> AcceptRelationCommand:
        return AcceptRelationCommand(relation_id=relation_id, acting_user_id=payload.acting_user_id)

    @staticmethod
    def to_leave_relation_command(relation_id: str, payload: LeaveRelationRequest) -> LeaveRelationCommand:
        return LeaveRelationCommand(relation_id=relation_id, acting_user_id=payload.acting_user_id)

    @staticmethod
    def to_list_trainer_clients_command(trainer_user_id: str, status: str) -> ListTrainerClientsCommand:
        return ListTrainerClientsCommand(trainer_user_id=trainer_user_id, status=status)

    @staticmethod
    def to_list_trainer_clients_with_filters_command(
        trainer_user_id: str,
        status: str,
        page: int | None,
        page_size: int | None,
        search: str | None,
    ) -> ListTrainerClientsCommand:
        return ListTrainerClientsCommand(
            trainer_user_id=trainer_user_id,
            status=status,
            page=page,
            page_size=page_size,
            search=search,
        )

    @staticmethod
    def to_list_discovery_profiles_command(
        page: int | None,
        page_size: int | None,
        search: str | None,
    ) -> ListDiscoveryProfilesCommand:
        return ListDiscoveryProfilesCommand(page=page, page_size=page_size, search=search)

    @staticmethod
    def to_list_incoming_invites_command(client_user_id: str) -> ListIncomingInvitesCommand:
        return ListIncomingInvitesCommand(client_user_id=client_user_id)

    @staticmethod
    def to_get_client_active_relation_command(client_user_id: str) -> GetClientActiveRelationCommand:
        return GetClientActiveRelationCommand(client_user_id=client_user_id)

    @staticmethod
    def to_get_trainer_funnel_command(trainer_user_id: str) -> GetTrainerFunnelCommand:
        return GetTrainerFunnelCommand(trainer_user_id=trainer_user_id)

    @staticmethod
    def to_check_profile_access_command(payload: CompatMembershipCheckRequest) -> CheckProfileAccessCommand:
        return CheckProfileAccessCommand(user_id=payload.user_id, allowed_roles=payload.allowed_roles)

    @staticmethod
    def to_profile_access_command(payload: ProfileAccessCheckRequest) -> CheckProfileAccessCommand:
        return CheckProfileAccessCommand(user_id=payload.user_id, allowed_roles=payload.allowed_roles)
