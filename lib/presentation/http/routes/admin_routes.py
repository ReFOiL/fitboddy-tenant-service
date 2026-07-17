from fastapi import APIRouter, Header, Query, Request

from presentation.http.schemas import (
    AdminProfileListResponse,
    AdminRelationListResponse,
    AdminSetPublicationRequest,
    AdminStatsResponse,
    DiscoveryProfileResponse,
    TrainerClientRelationResponse,
)


class AdminRoutes:
    def __init__(self) -> None:
        self.router = APIRouter(prefix="/api/v1/admin", tags=["admin"])
        self.router.add_api_route(
            "/marketplace/profiles",
            self.list_profiles,
            methods=["GET"],
            response_model=AdminProfileListResponse,
        )
        self.router.add_api_route(
            "/marketplace/profiles/{user_id}/publication",
            self.set_publication,
            methods=["PATCH"],
            response_model=DiscoveryProfileResponse,
        )
        self.router.add_api_route(
            "/marketplace/relations",
            self.list_relations,
            methods=["GET"],
            response_model=AdminRelationListResponse,
        )
        self.router.add_api_route(
            "/marketplace/relations/{relation_id}/force-leave",
            self.force_leave,
            methods=["POST"],
            response_model=TrainerClientRelationResponse,
        )
        self.router.add_api_route("/stats", self.stats, methods=["GET"], response_model=AdminStatsResponse)

    def list_profiles(
        self,
        request: Request,
        authorization: str = Header(default="", alias="Authorization"),
        role: str | None = Query(default=None),
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=20, ge=1, le=100),
    ) -> AdminProfileListResponse:
        return request.app.state.tenant_handler.admin_list_profiles(
            authorization=authorization,
            role=role,
            page=page,
            page_size=page_size,
        )

    def set_publication(
        self,
        user_id: str,
        payload: AdminSetPublicationRequest,
        request: Request,
        authorization: str = Header(default="", alias="Authorization"),
    ) -> DiscoveryProfileResponse:
        return request.app.state.tenant_handler.admin_set_publication(
            authorization=authorization,
            user_id=user_id,
            payload=payload,
        )

    def list_relations(
        self,
        request: Request,
        authorization: str = Header(default="", alias="Authorization"),
        status: str | None = Query(default=None),
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=20, ge=1, le=100),
    ) -> AdminRelationListResponse:
        return request.app.state.tenant_handler.admin_list_relations(
            authorization=authorization,
            status_filter=status,
            page=page,
            page_size=page_size,
        )

    def force_leave(
        self,
        relation_id: str,
        request: Request,
        authorization: str = Header(default="", alias="Authorization"),
    ) -> TrainerClientRelationResponse:
        return request.app.state.tenant_handler.admin_force_leave_relation(
            authorization=authorization,
            relation_id=relation_id,
        )

    def stats(
        self,
        request: Request,
        authorization: str = Header(default="", alias="Authorization"),
    ) -> AdminStatsResponse:
        return request.app.state.tenant_handler.admin_stats(authorization=authorization)
