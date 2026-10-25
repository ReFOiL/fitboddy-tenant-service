import re
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from application.gateways import AuthUser
from presentation.http.main import app


_CODE_PATTERN = re.compile(r"[2-9A-HJKMNP-Z]{6}")


def auth_as(user_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {user_id}"}


def put_profile(api: TestClient, user_id: str, role: str) -> None:
    response = api.put(
        f"/api/v1/marketplace/users/{user_id}/profile",
        json={"role": role, "is_visible": True, "looking_for_trainer": role == "client"},
    )
    assert response.status_code == 200


def issue_invite(api: TestClient, trainer_id: str) -> dict[str, str]:
    put_profile(api, trainer_id, "trainer")
    response = api.get("/api/v1/marketplace/trainers/me/invite-link", headers=auth_as(trainer_id))
    assert response.status_code == 200
    body = response.json()
    assert _CODE_PATTERN.fullmatch(body["code"])
    assert body["invite_path"] == f"/i/{body['code']}"
    return body


@pytest.fixture
def api(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    def fake_get_current_user(_self: object, access_token: str) -> AuthUser:
        return AuthUser(user_id=access_token, tenant_id="marketplace", role="client")

    monkeypatch.setattr("application.gateways.AuthGateway.get_current_user", fake_get_current_user)
    with TestClient(app) as test_client:
        yield test_client


def test_get_invite_link_creates_stable_code(api: TestClient) -> None:
    trainer_id = f"trainer_invite_{uuid4().hex}"
    assert api.get("/api/v1/marketplace/trainers/me/invite-link").status_code == 401

    client_id = f"client_invite_link_{uuid4().hex}"
    put_profile(api, client_id, "client")
    forbidden = api.get("/api/v1/marketplace/trainers/me/invite-link", headers=auth_as(client_id))
    assert forbidden.status_code == 403

    first = issue_invite(api, trainer_id)
    second = api.get("/api/v1/marketplace/trainers/me/invite-link", headers=auth_as(trainer_id))
    assert second.status_code == 200
    assert second.json() == first


def test_rotate_invite_link_invalidates_previous_code(api: TestClient) -> None:
    trainer_id = f"trainer_rotate_{uuid4().hex}"
    original = issue_invite(api, trainer_id)

    rotated = api.post("/api/v1/marketplace/trainers/me/invite-link/rotate", headers=auth_as(trainer_id))
    assert rotated.status_code == 200
    body = rotated.json()
    assert body["code"] != original["code"]
    assert body["invite_path"] == f"/i/{body['code']}"
    assert _CODE_PATTERN.fullmatch(body["code"])

    assert api.get(f"/api/v1/marketplace/invite/{original['code'].lower()}").status_code == 404
    resolved = api.get(f"/api/v1/marketplace/invite/{body['code'].lower()}")
    assert resolved.status_code == 200
    assert resolved.json()["trainer_user_id"] == trainer_id

    current = api.get("/api/v1/marketplace/trainers/me/invite-link", headers=auth_as(trainer_id))
    assert current.status_code == 200
    assert current.json() == body


def test_public_resolve_invite_code(api: TestClient) -> None:
    trainer_id = f"trainer_public_{uuid4().hex}"
    issued = issue_invite(api, trainer_id)

    resolved = api.get(f"/api/v1/marketplace/invite/{issued['code'].lower()}")
    assert resolved.status_code == 200
    assert resolved.json() == {
        "code": issued["code"],
        "trainer_user_id": trainer_id,
        "trainer_display_name": None,
        "trainer_login": None,
    }

    assert api.get("/api/v1/marketplace/invite/ZZZZZZ").status_code == 404
    assert api.get("/api/v1/marketplace/invite/IIIIII").status_code == 404


def test_accept_invite_code_creates_profile_for_new_client(api: TestClient) -> None:
    trainer_id = f"trainer_new_client_{uuid4().hex}"
    client_id = f"client_new_{uuid4().hex}"
    issued = issue_invite(api, trainer_id)
    accept_url = f"/api/v1/marketplace/invite/{issued['code'].lower()}/accept"

    assert api.post(accept_url).status_code == 401
    missing_profile = api.post(
        "/api/v1/marketplace/profiles/check",
        json={"user_id": client_id, "allowed_roles": ["client"]},
    )
    assert missing_profile.json()["exists"] is False

    accepted = api.post(accept_url, headers=auth_as(client_id))
    assert accepted.status_code == 200
    relation = accepted.json()
    assert relation["trainer_user_id"] == trainer_id
    assert relation["client_user_id"] == client_id
    assert relation["status"] == "active"
    assert relation["source"] == "invite_code"

    profile = api.post(
        "/api/v1/marketplace/profiles/check",
        json={"user_id": client_id, "allowed_roles": ["client"]},
    )
    assert profile.json() == {"exists": True, "role": "client"}

    clients = api.get(f"/api/v1/marketplace/trainers/{trainer_id}/clients?status=active")
    assert clients.status_code == 200
    assert [item["relation_id"] for item in clients.json()] == [relation["relation_id"]]

    funnel = api.get(f"/api/v1/marketplace/trainers/{trainer_id}/funnel")
    assert funnel.status_code == 200
    assert funnel.json()["invites_sent"] == 0
    assert funnel.json()["active_clients"] == 1


def test_accept_invite_code_for_existing_client(api: TestClient) -> None:
    trainer_id = f"trainer_existing_{uuid4().hex}"
    client_id = f"client_existing_{uuid4().hex}"
    issued = issue_invite(api, trainer_id)
    put_profile(api, client_id, "client")

    accepted = api.post(
        f"/api/v1/marketplace/invite/{issued['code']}/accept",
        headers=auth_as(client_id),
    )
    assert accepted.status_code == 200
    relation = accepted.json()
    assert relation["status"] == "active"
    assert relation["source"] == "invite_code"
    assert relation["client_user_id"] == client_id

    profile = api.post(
        "/api/v1/marketplace/profiles/check",
        json={"user_id": client_id, "allowed_roles": ["client"]},
    )
    assert profile.json() == {"exists": True, "role": "client"}


def test_accept_invite_code_reactivates_ended_relation(api: TestClient) -> None:
    trainer_id = f"trainer_rejoin_{uuid4().hex}"
    client_id = f"client_rejoin_{uuid4().hex}"
    issued = issue_invite(api, trainer_id)
    accept_url = f"/api/v1/marketplace/invite/{issued['code']}/accept"

    first = api.post(accept_url, headers=auth_as(client_id))
    assert first.status_code == 200
    relation_id = first.json()["relation_id"]

    left = api.post(f"/api/v1/marketplace/relations/{relation_id}/leave", headers=auth_as(client_id))
    assert left.status_code == 200
    assert left.json()["status"] == "ended"

    again = api.post(accept_url, headers=auth_as(client_id))
    assert again.status_code == 200
    assert again.json()["relation_id"] == relation_id
    assert again.json()["status"] == "active"
    assert again.json()["source"] == "invite_code"


def test_accept_invite_code_is_idempotent_for_same_trainer(api: TestClient) -> None:
    trainer_id = f"trainer_same_{uuid4().hex}"
    client_id = f"client_same_{uuid4().hex}"
    issued = issue_invite(api, trainer_id)
    put_profile(api, client_id, "client")

    created = api.post(
        "/api/v1/marketplace/relations",
        headers=auth_as(trainer_id),
        json={"trainer_user_id": trainer_id, "client_user_id": client_id, "mode": "direct"},
    )
    assert created.status_code == 201
    relation_id = created.json()["relation_id"]

    accept_url = f"/api/v1/marketplace/invite/{issued['code']}/accept"
    first = api.post(accept_url, headers=auth_as(client_id))
    second = api.post(accept_url, headers=auth_as(client_id))
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["relation_id"] == relation_id
    assert second.json()["relation_id"] == relation_id
    assert first.json()["status"] == "active"
    assert first.json()["source"] == "direct"
    assert second.json()["source"] == "direct"

    clients = api.get(f"/api/v1/marketplace/trainers/{trainer_id}/clients?status=active")
    assert [item["relation_id"] for item in clients.json()] == [relation_id]


def test_accept_invite_code_conflicts_when_linked_to_another_trainer(api: TestClient) -> None:
    trainer_id = f"trainer_conflict_{uuid4().hex}"
    other_trainer_id = f"trainer_other_{uuid4().hex}"
    client_id = f"client_conflict_{uuid4().hex}"
    issued = issue_invite(api, trainer_id)
    put_profile(api, other_trainer_id, "trainer")
    put_profile(api, client_id, "client")

    created = api.post(
        "/api/v1/marketplace/relations",
        headers=auth_as(other_trainer_id),
        json={
            "trainer_user_id": other_trainer_id,
            "client_user_id": client_id,
            "mode": "direct",
        },
    )
    assert created.status_code == 201
    relation_id = created.json()["relation_id"]

    conflict = api.post(
        f"/api/v1/marketplace/invite/{issued['code']}/accept",
        headers=auth_as(client_id),
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"] == {
        "reason": "already_linked",
        "message": "client already linked to another trainer",
        "current_trainer_user_id": other_trainer_id,
    }

    active = api.get(f"/api/v1/marketplace/clients/{client_id}/active-relation")
    assert active.status_code == 200
    assert active.json()["relation_id"] == relation_id
    assert active.json()["trainer_user_id"] == other_trainer_id

    invited_clients = api.get(f"/api/v1/marketplace/trainers/{trainer_id}/clients?status=active")
    assert invited_clients.json() == []


def test_accept_invite_code_force_switches_trainer(api: TestClient) -> None:
    trainer_id = f"trainer_force_{uuid4().hex}"
    other_trainer_id = f"trainer_force_other_{uuid4().hex}"
    client_id = f"client_force_{uuid4().hex}"
    issued = issue_invite(api, trainer_id)
    put_profile(api, other_trainer_id, "trainer")
    put_profile(api, client_id, "client")
    created = api.post(
        "/api/v1/marketplace/relations",
        headers=auth_as(other_trainer_id),
        json={
            "trainer_user_id": other_trainer_id,
            "client_user_id": client_id,
            "mode": "direct",
        },
    )
    assert created.status_code == 201

    switched = api.post(
        f"/api/v1/marketplace/invite/{issued['code']}/accept",
        headers=auth_as(client_id),
        params={"force": True},
    )
    assert switched.status_code == 200
    relation = switched.json()
    assert relation["trainer_user_id"] == trainer_id
    assert relation["client_user_id"] == client_id
    assert relation["status"] == "active"
    assert relation["source"] == "invite_code"

    active = api.get(f"/api/v1/marketplace/clients/{client_id}/active-relation")
    assert active.json()["trainer_user_id"] == trainer_id
    ended = api.get(f"/api/v1/marketplace/trainers/{other_trainer_id}/clients?status=ended")
    assert any(item["client_user_id"] == client_id and item["status"] == "ended" for item in ended.json())


def test_trainer_cannot_accept_invite_code(api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    trainer_id = f"trainer_owner_{uuid4().hex}"
    other_trainer_id = f"trainer_blocked_{uuid4().hex}"
    issued = issue_invite(api, trainer_id)
    put_profile(api, other_trainer_id, "trainer")
    accept_url = f"/api/v1/marketplace/invite/{issued['code']}/accept"

    profile_block = api.post(accept_url, headers=auth_as(other_trainer_id))
    assert profile_block.status_code == 403
    own_code = api.post(accept_url, headers=auth_as(trainer_id))
    assert own_code.status_code == 403

    sneaky_id = f"trainer_token_{uuid4().hex}"

    def fake_get_current_user(_self: object, access_token: str) -> AuthUser:
        role = "trainer" if access_token == sneaky_id else "client"
        return AuthUser(user_id=access_token, tenant_id="marketplace", role=role)

    monkeypatch.setattr("application.gateways.AuthGateway.get_current_user", fake_get_current_user)
    token_block = api.post(accept_url, headers=auth_as(sneaky_id))
    assert token_block.status_code == 403
    profile = api.post(
        "/api/v1/marketplace/profiles/check",
        json={"user_id": sneaky_id, "allowed_roles": []},
    )
    assert profile.json()["exists"] is False

    active = api.get(f"/api/v1/marketplace/clients/{other_trainer_id}/active-relation")
    assert active.status_code == 404
