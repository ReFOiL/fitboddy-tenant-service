from fastapi import HTTPException, status

from application.errors import TenantError
from application.runtime import TenantApplicationRuntime
from presentation.http.error_translator import ErrorTranslator
from presentation.http.request_factory import TenantRequestFactory
from presentation.http.response_factory import TenantResponseFactory
from application.gateways import AuthUser
from presentation.http.schemas import (
    AdminProfileListResponse,
    AdminRelationListResponse,
    AdminSetPublicationRequest,
    AdminStatsResponse,
    CompatMembershipCheckRequest,
    CompatMembershipCheckResponse,
    CreateRelationRequest,
    DiscoveryProfileResponse,
    ProfileAccessCheckRequest,
    ProfileAccessCheckResponse,
    TrainerClientRelationResponse,
    TrainerFunnelResponse,
    TrainerPublicationStatusResponse,
    UpsertDiscoveryProfileRequest,
)


class TenantHttpHandler:
    def __init__(
        self,
        runtime: TenantApplicationRuntime,
        request_factory: TenantRequestFactory,
        response_factory: TenantResponseFactory,
        error_translator: ErrorTranslator,
    ) -> None:
        self._runtime = runtime
        self._request_factory = request_factory
        self._response_factory = response_factory
        self._error_translator = error_translator

    def health(self) -> dict[str, str]:
        return {"status": "ok"}

    def ready(self) -> dict[str, str]:
        self._runtime.check_ready()
        return {"status": "ready"}

    def upsert_profile(self, user_id: str, payload: UpsertDiscoveryProfileRequest) -> DiscoveryProfileResponse:
        try:
            with self._runtime.tenant_service_scope() as tenant_service:
                profile = tenant_service.upsert_profile(self._request_factory.to_upsert_profile_command(user_id, payload))
                return self._response_factory.from_domain_profile(profile)
        except TenantError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def list_trainers(
        self,
        *,
        page: int | None = None,
        page_size: int | None = None,
        search: str | None = None,
    ) -> tuple[list[DiscoveryProfileResponse], int]:
        try:
            with self._runtime.tenant_service_scope() as tenant_service:
                profiles, total = tenant_service.list_trainers(
                    self._request_factory.to_list_discovery_profiles_command(
                        page=page,
                        page_size=page_size,
                        search=search,
                    )
                )
                return [self._response_factory.from_domain_profile(profile) for profile in profiles], total
        except TenantError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def create_relation(self, authorization: str, payload: CreateRelationRequest) -> TrainerClientRelationResponse:
        actor = self._require_current_user(authorization)
        try:
            with self._runtime.tenant_service_scope() as tenant_service:
                relation = tenant_service.create_relation(
                    self._request_factory.to_create_relation_command(payload, actor.user_id)
                )
                return self._response_factory.from_domain_relation(relation)
        except TenantError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def accept_relation(self, authorization: str, relation_id: str) -> TrainerClientRelationResponse:
        actor = self._require_current_user(authorization)
        try:
            with self._runtime.tenant_service_scope() as tenant_service:
                relation = tenant_service.accept_relation(
                    self._request_factory.to_accept_relation_command(relation_id, actor.user_id)
                )
                return self._response_factory.from_domain_relation(relation)
        except TenantError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def leave_relation(self, authorization: str, relation_id: str) -> TrainerClientRelationResponse:
        actor = self._require_current_user(authorization)
        try:
            with self._runtime.tenant_service_scope() as tenant_service:
                relation = tenant_service.leave_relation(
                    self._request_factory.to_leave_relation_command(relation_id, actor.user_id)
                )
                return self._response_factory.from_domain_relation(relation)
        except TenantError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def list_trainer_clients(
        self,
        trainer_user_id: str,
        status: str,
        *,
        page: int | None = None,
        page_size: int | None = None,
        search: str | None = None,
    ) -> tuple[list[TrainerClientRelationResponse], int]:
        try:
            with self._runtime.tenant_service_scope() as tenant_service:
                relations, total = tenant_service.list_trainer_clients(
                    self._request_factory.to_list_trainer_clients_with_filters_command(
                        trainer_user_id=trainer_user_id,
                        status=status,
                        page=page,
                        page_size=page_size,
                        search=search,
                    )
                )
                return [self._response_factory.from_domain_relation(relation) for relation in relations], total
        except TenantError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def list_incoming_invites(self, client_user_id: str) -> list[TrainerClientRelationResponse]:
        try:
            with self._runtime.tenant_service_scope() as tenant_service:
                relations = tenant_service.list_incoming_invites(
                    self._request_factory.to_list_incoming_invites_command(client_user_id)
                )
                return [self._response_factory.from_domain_relation(relation) for relation in relations]
        except TenantError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def get_client_active_relation(self, client_user_id: str) -> TrainerClientRelationResponse:
        try:
            with self._runtime.tenant_service_scope() as tenant_service:
                relation = tenant_service.get_client_active_relation(
                    self._request_factory.to_get_client_active_relation_command(client_user_id)
                )
                return self._response_factory.from_domain_relation(relation)
        except TenantError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def get_trainer_funnel(self, trainer_user_id: str) -> TrainerFunnelResponse:
        try:
            with self._runtime.tenant_service_scope() as tenant_service:
                funnel = tenant_service.get_trainer_funnel(
                    self._request_factory.to_get_trainer_funnel_command(trainer_user_id)
                )
                return self._response_factory.from_domain_trainer_funnel(funnel)
        except TenantError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def get_trainer_publication_status(self, trainer_user_id: str) -> TrainerPublicationStatusResponse:
        try:
            with self._runtime.tenant_service_scope() as tenant_service:
                is_published = tenant_service.get_trainer_publication_status(
                    self._request_factory.to_get_trainer_publication_status_command(trainer_user_id)
                )
                return TrainerPublicationStatusResponse(
                    trainer_user_id=trainer_user_id,
                    is_published=is_published,
                )
        except TenantError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def compat_check_membership(self, payload: CompatMembershipCheckRequest) -> CompatMembershipCheckResponse:
        try:
            with self._runtime.tenant_service_scope() as tenant_service:
                profile = tenant_service.check_profile_access(
                    self._request_factory.to_check_profile_access_command(payload)
                )
                if profile is None:
                    return CompatMembershipCheckResponse(is_member=False, role=None)
                return CompatMembershipCheckResponse(is_member=True, role=profile.role)
        except TenantError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def check_profile_access(self, payload: ProfileAccessCheckRequest) -> ProfileAccessCheckResponse:
        try:
            with self._runtime.tenant_service_scope() as tenant_service:
                profile = tenant_service.check_profile_access(self._request_factory.to_profile_access_command(payload))
                if profile is None:
                    return ProfileAccessCheckResponse(exists=False, role=None)
                return ProfileAccessCheckResponse(exists=True, role=profile.role)
        except TenantError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def admin_list_profiles(
        self,
        *,
        authorization: str,
        role: str | None,
        page: int,
        page_size: int,
    ) -> AdminProfileListResponse:
        self._require_platform_admin(authorization)
        try:
            with self._runtime.tenant_service_scope() as tenant_service:
                items, total = tenant_service.admin_list_profiles(role=role, page=page, page_size=page_size)
                return AdminProfileListResponse(
                    items=[self._response_factory.from_domain_profile(item) for item in items],
                    total=total,
                    page=page,
                    page_size=page_size,
                )
        except TenantError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def admin_set_publication(
        self,
        *,
        authorization: str,
        user_id: str,
        payload: AdminSetPublicationRequest,
    ) -> DiscoveryProfileResponse:
        self._require_platform_admin(authorization)
        try:
            with self._runtime.tenant_service_scope() as tenant_service:
                profile = tenant_service.admin_set_publication(user_id, payload.is_visible)
                return self._response_factory.from_domain_profile(profile)
        except TenantError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def admin_list_relations(
        self,
        *,
        authorization: str,
        status_filter: str | None,
        page: int,
        page_size: int,
    ) -> AdminRelationListResponse:
        self._require_platform_admin(authorization)
        try:
            with self._runtime.tenant_service_scope() as tenant_service:
                items, total = tenant_service.admin_list_relations(
                    status=status_filter,
                    page=page,
                    page_size=page_size,
                )
                return AdminRelationListResponse(
                    items=[self._response_factory.from_domain_relation(item) for item in items],
                    total=total,
                    page=page,
                    page_size=page_size,
                )
        except TenantError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def admin_force_leave_relation(self, *, authorization: str, relation_id: str) -> TrainerClientRelationResponse:
        self._require_platform_admin(authorization)
        try:
            with self._runtime.tenant_service_scope() as tenant_service:
                relation = tenant_service.admin_force_leave_relation(relation_id)
                return self._response_factory.from_domain_relation(relation)
        except TenantError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def admin_stats(self, *, authorization: str) -> AdminStatsResponse:
        self._require_platform_admin(authorization)
        try:
            with self._runtime.tenant_service_scope() as tenant_service:
                stats = tenant_service.admin_stats()
                return AdminStatsResponse(**stats)
        except TenantError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def _require_current_user(self, authorization: str) -> AuthUser:
        access_token = authorization.removeprefix("Bearer ").strip()
        if not access_token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Bearer token.")
        try:
            return self._runtime.auth_gateway.get_current_user(access_token)
        except TenantError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def _require_platform_admin(self, authorization: str) -> None:
        access_token = authorization.removeprefix("Bearer ").strip()
        if not access_token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Bearer token.")
        try:
            self._runtime.auth_gateway.require_platform_admin(access_token)
        except TenantError as exc:
            self._error_translator.raise_http_error(exc)
