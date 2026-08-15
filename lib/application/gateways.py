from __future__ import annotations

from dataclasses import dataclass
import json
from urllib import error, request

from application.errors import ForbiddenError, UnauthorizedError


@dataclass(frozen=True)
class AuthUser:
    user_id: str
    tenant_id: str
    role: str


class ProfileGateway:
    def __init__(self, profile_service_url: str, service_token: str = "") -> None:
        self._profile_service_url = profile_service_url.rstrip("/")
        self._service_token = service_token

    def get_full_names_by_user_ids(self, user_ids: list[str]) -> dict[str, str]:
        if not user_ids:
            return {}
        payload = json.dumps({"user_ids": user_ids}).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self._service_token:
            headers["X-Service-Token"] = self._service_token
        req = request.Request(
            f"{self._profile_service_url}/api/v1/profiles/internal/summaries",
            data=payload,
            headers=headers,
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=5) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (error.URLError, error.HTTPError, json.JSONDecodeError):
            return {}
        items = body.get("items")
        if not isinstance(items, list):
            return {}
        result: dict[str, str] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            user_id = item.get("user_id")
            full_name = item.get("full_name")
            if isinstance(user_id, str) and isinstance(full_name, str) and full_name.strip():
                result[user_id] = full_name.strip()
        return result


class AuthGateway:
    def __init__(self, auth_service_url: str) -> None:
        self._auth_service_url = auth_service_url.rstrip("/")

    def get_current_user(self, access_token: str) -> AuthUser:
        req = request.Request(
            f"{self._auth_service_url}/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
            method="GET",
        )
        try:
            with request.urlopen(req, timeout=5) as response:
                body = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            if exc.code == 401:
                raise UnauthorizedError("invalid access token") from exc
            raise UnauthorizedError("auth-service unavailable") from exc
        except (error.URLError, json.JSONDecodeError) as exc:
            raise UnauthorizedError("auth-service unavailable") from exc
        return AuthUser(user_id=body["user_id"], tenant_id=body["tenant_id"], role=body["role"])

    def require_platform_admin(self, access_token: str) -> AuthUser:
        user = self.get_current_user(access_token)
        if user.role != "platform_admin":
            raise ForbiddenError("platform_admin role required")
        return user

    def get_logins_by_user_ids(self, user_ids: list[str]) -> dict[str, str]:
        if not user_ids:
            return {}
        payload = json.dumps({"user_ids": user_ids}).encode("utf-8")
        req = request.Request(
            f"{self._auth_service_url}/api/v1/auth/internal/summaries",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=5) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (error.URLError, error.HTTPError, json.JSONDecodeError):
            return {}
        items = body.get("items")
        if not isinstance(items, list):
            return {}
        result: dict[str, str] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            user_id = item.get("user_id")
            login = item.get("login")
            if isinstance(user_id, str) and isinstance(login, str) and login.strip():
                result[user_id] = login.strip()
        return result
