from fastapi import APIRouter, Request, status

from presentation.http.schemas import (
    AcceptRelationRequest,
    CompatMembershipCheckRequest,
    CompatMembershipCheckResponse,
    CreateRelationRequest,
    DiscoveryProfileResponse,
    LeaveRelationRequest,
    ProfileAccessCheckRequest,
    ProfileAccessCheckResponse,
    TrainerClientRelationResponse,
    TrainerFunnelResponse,
    UpsertDiscoveryProfileRequest,
)


class TenantRoutes:
    def __init__(self) -> None:
        self.router = APIRouter(prefix="/api/v1", tags=["marketplace"])
        self.router.add_api_route(
            "/marketplace/users/{user_id}/profile",
            self.upsert_profile,
            methods=["PUT"],
            response_model=DiscoveryProfileResponse,
        )
        self.router.add_api_route(
            "/marketplace/trainers", self.list_trainers, methods=["GET"], response_model=list[DiscoveryProfileResponse]
        )
        self.router.add_api_route(
            "/marketplace/clients/looking",
            self.list_clients_looking_for_trainer,
            methods=["GET"],
            response_model=list[DiscoveryProfileResponse],
        )
        self.router.add_api_route(
            "/marketplace/relations",
            self.create_relation,
            methods=["POST"],
            response_model=TrainerClientRelationResponse,
            status_code=status.HTTP_201_CREATED,
        )
        self.router.add_api_route(
            "/marketplace/relations/{relation_id}/accept",
            self.accept_relation,
            methods=["POST"],
            response_model=TrainerClientRelationResponse,
        )
        self.router.add_api_route(
            "/marketplace/relations/{relation_id}/leave",
            self.leave_relation,
            methods=["POST"],
            response_model=TrainerClientRelationResponse,
        )
        self.router.add_api_route(
            "/marketplace/trainers/{trainer_user_id}/clients",
            self.list_trainer_clients,
            methods=["GET"],
            response_model=list[TrainerClientRelationResponse],
        )
        self.router.add_api_route(
            "/marketplace/trainers/{trainer_user_id}/funnel",
            self.get_trainer_funnel,
            methods=["GET"],
            response_model=TrainerFunnelResponse,
        )
        self.router.add_api_route(
            "/marketplace/clients/{client_user_id}/invites",
            self.list_incoming_invites,
            methods=["GET"],
            response_model=list[TrainerClientRelationResponse],
        )
        self.router.add_api_route(
            "/marketplace/clients/{client_user_id}/active-relation",
            self.get_client_active_relation,
            methods=["GET"],
            response_model=TrainerClientRelationResponse,
        )
        self.router.add_api_route(
            "/marketplace/profiles/check",
            self.check_profile_access,
            methods=["POST"],
            response_model=ProfileAccessCheckResponse,
        )
        # Temporary compatibility endpoint for existing profile-service checks.
        self.router.add_api_route(
            "/tenants/{tenant_id}/members/check",
            self.compat_check_membership,
            methods=["POST"],
            response_model=CompatMembershipCheckResponse,
        )

    @staticmethod
    def upsert_profile(request: Request, user_id: str, payload: UpsertDiscoveryProfileRequest) -> DiscoveryProfileResponse:
        return request.app.state.tenant_handler.upsert_profile(user_id, payload)

    @staticmethod
    def list_trainers(request: Request) -> list[DiscoveryProfileResponse]:
        return request.app.state.tenant_handler.list_trainers()

    @staticmethod
    def list_clients_looking_for_trainer(request: Request) -> list[DiscoveryProfileResponse]:
        return request.app.state.tenant_handler.list_clients_looking_for_trainer()

    @staticmethod
    def create_relation(request: Request, payload: CreateRelationRequest) -> TrainerClientRelationResponse:
        return request.app.state.tenant_handler.create_relation(payload)

    @staticmethod
    def accept_relation(
        request: Request, relation_id: str, payload: AcceptRelationRequest
    ) -> TrainerClientRelationResponse:
        return request.app.state.tenant_handler.accept_relation(relation_id, payload)

    @staticmethod
    def leave_relation(request: Request, relation_id: str, payload: LeaveRelationRequest) -> TrainerClientRelationResponse:
        return request.app.state.tenant_handler.leave_relation(relation_id, payload)

    @staticmethod
    def list_trainer_clients(
        request: Request, trainer_user_id: str, status: str = "active"
    ) -> list[TrainerClientRelationResponse]:
        return request.app.state.tenant_handler.list_trainer_clients(trainer_user_id, status)

    @staticmethod
    def list_incoming_invites(request: Request, client_user_id: str) -> list[TrainerClientRelationResponse]:
        return request.app.state.tenant_handler.list_incoming_invites(client_user_id)

    @staticmethod
    def get_client_active_relation(request: Request, client_user_id: str) -> TrainerClientRelationResponse:
        return request.app.state.tenant_handler.get_client_active_relation(client_user_id)

    @staticmethod
    def get_trainer_funnel(request: Request, trainer_user_id: str) -> TrainerFunnelResponse:
        return request.app.state.tenant_handler.get_trainer_funnel(trainer_user_id)

    @staticmethod
    def check_profile_access(
        request: Request, payload: ProfileAccessCheckRequest
    ) -> ProfileAccessCheckResponse:
        return request.app.state.tenant_handler.check_profile_access(payload)

    @staticmethod
    def compat_check_membership(
        request: Request, tenant_id: str, payload: CompatMembershipCheckRequest
    ) -> CompatMembershipCheckResponse:
        _ = tenant_id
        return request.app.state.tenant_handler.compat_check_membership(payload)
