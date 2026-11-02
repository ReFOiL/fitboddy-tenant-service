from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from application.gateways import AuthUser
from presentation.http.main import app
from presentation.http.rate_limit import SlidingWindowRateLimiter, caller_keys, list_route_limiter


def auth_as(user_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {user_id}"}


def role_for(access_token: str) -> str:
    if access_token.startswith("admin_"):
        return "platform_admin"
    return "client"


@pytest.fixture
def api(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    def fake_get_current_user(_self: object, access_token: str) -> AuthUser:
        return AuthUser(user_id=access_token, tenant_id="marketplace", role=role_for(access_token))

    def fake_logins(_self: object, user_ids: list[str]) -> dict[str, str]:
        return {user_id: f"login-{user_id}" for user_id in user_ids}

    def fake_names(_self: object, user_ids: list[str]) -> dict[str, str]:
        return {user_id: f"Name {user_id}" for user_id in user_ids}

    monkeypatch.setattr("application.gateways.AuthGateway.get_current_user", fake_get_current_user)
    monkeypatch.setattr("application.gateways.AuthGateway.get_logins_by_user_ids", fake_logins)
    monkeypatch.setattr("application.gateways.ProfileGateway.get_full_names_by_user_ids", fake_names)
    with TestClient(app) as test_client:
        yield test_client


def put_profile(api: TestClient, user_id: str, role: str) -> None:
    response = api.put(
        f"/api/v1/marketplace/users/{user_id}/profile",
        json={"role": role, "is_visible": True, "looking_for_trainer": role == "client"},
    )
    assert response.status_code == 200


def link(api: TestClient, trainer_id: str, client_id: str, mode: str = "direct") -> dict[str, str]:
    response = api.post(
        "/api/v1/marketplace/relations",
        headers=auth_as(trainer_id),
        json={"trainer_user_id": trainer_id, "client_user_id": client_id, "mode": mode},
    )
    assert response.status_code == 201
    body = response.json()
    assert isinstance(body, dict)
    return body


def test_relation_reads_require_owner_and_hide_other_logins(api: TestClient) -> None:
    trainer_id = f"trainer_acl_{uuid4().hex}"
    invited_client_id = f"client_invited_{uuid4().hex}"
    active_client_id = f"client_active_{uuid4().hex}"
    other_trainer_id = f"trainer_other_{uuid4().hex}"
    other_client_id = f"client_other_{uuid4().hex}"
    put_profile(api, trainer_id, "trainer")
    put_profile(api, invited_client_id, "client")
    put_profile(api, active_client_id, "client")
    put_profile(api, other_trainer_id, "trainer")
    put_profile(api, other_client_id, "client")
    invited = link(api, trainer_id, invited_client_id, mode="invite")
    active = link(api, trainer_id, active_client_id, mode="direct")

    clients_url = f"/api/v1/marketplace/trainers/{trainer_id}/clients?status=active"
    invites_url = f"/api/v1/marketplace/clients/{invited_client_id}/invites"
    active_url = f"/api/v1/marketplace/clients/{active_client_id}/active-relation"
    funnel_url = f"/api/v1/marketplace/trainers/{trainer_id}/funnel"

    for url in (clients_url, invites_url, active_url, funnel_url):
        anonymous = api.get(url)
        assert anonymous.status_code == 401
        assert "login-" not in anonymous.text

    forbidden_clients = api.get(clients_url, headers=auth_as(other_trainer_id))
    assert forbidden_clients.status_code == 403
    assert "login-" not in forbidden_clients.text
    assert api.get(clients_url, headers=auth_as(invited_client_id)).status_code == 403
    assert api.get(funnel_url, headers=auth_as(other_trainer_id)).status_code == 403
    assert api.get(funnel_url, headers=auth_as(active_client_id)).status_code == 403

    forbidden_invites = api.get(invites_url, headers=auth_as(trainer_id))
    assert forbidden_invites.status_code == 403
    assert "login-" not in forbidden_invites.text
    assert api.get(invites_url, headers=auth_as(other_client_id)).status_code == 403
    assert api.get(active_url, headers=auth_as(trainer_id)).status_code == 403
    assert api.get(active_url, headers=auth_as(other_client_id)).status_code == 403

    own_clients = api.get(clients_url, headers=auth_as(trainer_id))
    assert own_clients.status_code == 200
    assert [item["relation_id"] for item in own_clients.json()] == [active["relation_id"]]
    assert own_clients.json()[0]["client_user_id"] == active_client_id
    assert own_clients.json()[0]["trainer_login"] == f"login-{trainer_id}"
    assert own_clients.json()[0]["client_login"] is None
    assert own_clients.json()[0]["client_display_name"] == f"Name {active_client_id}"
    assert own_clients.headers["x-page"] == "1"
    assert own_clients.headers["x-page-size"] == "50"
    assert own_clients.headers["x-total-count"] == "1"

    other_clients = api.get(
        f"/api/v1/marketplace/trainers/{other_trainer_id}/clients?status=active",
        headers=auth_as(other_trainer_id),
    )
    assert other_clients.status_code == 200
    assert other_clients.json() == []

    own_invites = api.get(invites_url, headers=auth_as(invited_client_id))
    assert own_invites.status_code == 200
    assert [item["relation_id"] for item in own_invites.json()] == [invited["relation_id"]]
    assert own_invites.json()[0]["client_login"] == f"login-{invited_client_id}"
    assert own_invites.json()[0]["trainer_login"] is None
    assert own_invites.headers["x-page-size"] == "50"

    other_invites = api.get(
        f"/api/v1/marketplace/clients/{other_client_id}/invites",
        headers=auth_as(other_client_id),
    )
    assert other_invites.status_code == 200
    assert other_invites.json() == []

    own_active = api.get(active_url, headers=auth_as(active_client_id))
    assert own_active.status_code == 200
    assert own_active.json()["relation_id"] == active["relation_id"]
    assert own_active.json()["client_login"] == f"login-{active_client_id}"
    assert own_active.json()["trainer_login"] is None

    own_funnel = api.get(funnel_url, headers=auth_as(trainer_id))
    assert own_funnel.status_code == 200
    assert own_funnel.json()["trainer_user_id"] == trainer_id
    assert own_funnel.json()["active_clients"] == 1

    admin_id = f"admin_{uuid4().hex}"
    admin_clients = api.get(clients_url, headers=auth_as(admin_id))
    assert admin_clients.status_code == 200
    assert admin_clients.json()[0]["trainer_login"] == f"login-{trainer_id}"
    assert admin_clients.json()[0]["client_login"] == f"login-{active_client_id}"
    admin_invites = api.get(invites_url, headers=auth_as(admin_id))
    assert admin_invites.status_code == 200
    assert admin_invites.json()[0]["trainer_login"] == f"login-{trainer_id}"
    assert admin_invites.json()[0]["client_login"] == f"login-{invited_client_id}"
    admin_active = api.get(active_url, headers=auth_as(admin_id))
    assert admin_active.status_code == 200
    assert admin_active.json()["trainer_login"] == f"login-{trainer_id}"
    assert admin_active.json()["client_login"] == f"login-{active_client_id}"
    assert api.get(funnel_url, headers=auth_as(admin_id)).status_code == 200

    too_big = api.get(f"{clients_url}&page_size=51", headers=auth_as(trainer_id))
    assert too_big.status_code == 422


def test_omitted_page_cannot_dump_trainer_clients(api: TestClient) -> None:
    trainer_id = f"trainer_cap_{uuid4().hex}"
    put_profile(api, trainer_id, "trainer")
    for index in range(51):
        client_id = f"client_cap_{trainer_id}_{index}"
        put_profile(api, client_id, "client")
        link(api, trainer_id, client_id)

    listed = api.get(
        f"/api/v1/marketplace/trainers/{trainer_id}/clients?status=active",
        headers=auth_as(trainer_id),
    )
    assert listed.status_code == 200
    assert len(listed.json()) == 50
    assert listed.headers["x-total-count"] == "51"
    assert listed.headers["x-page"] == "1"
    assert listed.headers["x-page-size"] == "50"

    second_page = api.get(
        f"/api/v1/marketplace/trainers/{trainer_id}/clients?status=active&page=2",
        headers=auth_as(trainer_id),
    )
    assert second_page.status_code == 200
    assert len(second_page.json()) == 1
    assert second_page.headers["x-total-count"] == "51"
    listed_ids = {item["client_user_id"] for item in listed.json()}
    assert second_page.json()[0]["client_user_id"] not in listed_ids


def test_list_routes_are_rate_limited(api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    trainer_id = f"trainer_rate_{uuid4().hex}"
    put_profile(api, trainer_id, "trainer")
    url = f"/api/v1/marketplace/trainers/{trainer_id}/clients?status=active"
    list_route_limiter.reset()
    monkeypatch.setattr(list_route_limiter, "_limit", 1)
    try:
        first = api.get(url, headers=auth_as(trainer_id))
        second = api.get(url, headers=auth_as(trainer_id))
        assert first.status_code == 200
        assert second.status_code == 429
        assert second.json()["detail"] == "rate limit exceeded"
    finally:
        list_route_limiter.reset()


def test_sliding_window_limiter_isolates_keys() -> None:
    limiter = SlidingWindowRateLimiter(limit=1, window_seconds=60)
    assert limiter.allow(["ip:a", "token:1"]) is True
    assert limiter.allow(["ip:a", "token:2"]) is False
    assert limiter.allow(["ip:b", "token:2"]) is True
    assert limiter.allow(["ip:b"]) is False

    keys = caller_keys(host="10.0.0.1", authorization="Bearer super-secret")
    assert keys[0] == "ip:10.0.0.1"
    assert keys[1].startswith("token:")
    assert "super-secret" not in keys[1]
