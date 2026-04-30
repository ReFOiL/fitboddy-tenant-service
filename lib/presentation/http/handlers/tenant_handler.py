from application.errors import TenantError
from application.runtime import TenantApplicationRuntime
from presentation.http.error_translator import ErrorTranslator
from presentation.http.request_factory import TenantRequestFactory
from presentation.http.response_factory import TenantResponseFactory
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

    def list_trainers(self) -> list[DiscoveryProfileResponse]:
        try:
            with self._runtime.tenant_service_scope() as tenant_service:
                profiles = tenant_service.list_trainers()
                return [self._response_factory.from_domain_profile(profile) for profile in profiles]
        except TenantError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def list_clients_looking_for_trainer(self) -> list[DiscoveryProfileResponse]:
        try:
            with self._runtime.tenant_service_scope() as tenant_service:
                profiles = tenant_service.list_clients_looking_for_trainer()
                return [self._response_factory.from_domain_profile(profile) for profile in profiles]
        except TenantError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def create_relation(self, payload: CreateRelationRequest) -> TrainerClientRelationResponse:
        try:
            with self._runtime.tenant_service_scope() as tenant_service:
                relation = tenant_service.create_relation(self._request_factory.to_create_relation_command(payload))
                return self._response_factory.from_domain_relation(relation)
        except TenantError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def accept_relation(self, relation_id: str, payload: AcceptRelationRequest) -> TrainerClientRelationResponse:
        try:
            with self._runtime.tenant_service_scope() as tenant_service:
                relation = tenant_service.accept_relation(
                    self._request_factory.to_accept_relation_command(relation_id, payload)
                )
                return self._response_factory.from_domain_relation(relation)
        except TenantError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def leave_relation(self, relation_id: str, payload: LeaveRelationRequest) -> TrainerClientRelationResponse:
        try:
            with self._runtime.tenant_service_scope() as tenant_service:
                relation = tenant_service.leave_relation(
                    self._request_factory.to_leave_relation_command(relation_id, payload)
                )
                return self._response_factory.from_domain_relation(relation)
        except TenantError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def list_trainer_clients(self, trainer_user_id: str, status: str) -> list[TrainerClientRelationResponse]:
        try:
            with self._runtime.tenant_service_scope() as tenant_service:
                relations = tenant_service.list_trainer_clients(
                    self._request_factory.to_list_trainer_clients_command(trainer_user_id, status)
                )
                return [self._response_factory.from_domain_relation(relation) for relation in relations]
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
