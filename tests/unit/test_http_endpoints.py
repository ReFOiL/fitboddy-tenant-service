from fastapi.testclient import TestClient
import pytest
from uuid import uuid4

from application.gateways import AuthUser
from presentation.http.main import app


client: TestClient


def auth_as(user_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {user_id}"}


@pytest.fixture(autouse=True)
def setup_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    def fake_get_current_user(_self: object, access_token: str) -> AuthUser:
        return AuthUser(user_id=access_token, tenant_id="marketplace", role="client")

    monkeypatch.setattr("application.gateways.AuthGateway.get_current_user", fake_get_current_user)
    with TestClient(app) as test_client:
        global client
        client = test_client
        yield test_client


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready() -> None:
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_upsert_profile_and_list_trainers() -> None:
    upsert_response = client.put(
        "/api/v1/marketplace/users/trainer_1/profile",
        json={"role": "trainer", "is_visible": True, "looking_for_trainer": False},
    )
    assert upsert_response.status_code == 200
    assert upsert_response.json()["role"] == "trainer"

    trainers_response = client.get("/api/v1/marketplace/trainers")
    assert trainers_response.status_code == 200
    trainers = trainers_response.json()
    assert any(item["user_id"] == "trainer_1" for item in trainers)


def test_list_trainers_returns_only_published_profiles() -> None:
    visible_trainer_id = f"trainer_visible_{uuid4().hex}"
    hidden_trainer_id = f"trainer_hidden_{uuid4().hex}"

    client.put(
        f"/api/v1/marketplace/users/{visible_trainer_id}/profile",
        json={"role": "trainer", "is_visible": True, "looking_for_trainer": False},
    )
    client.put(
        f"/api/v1/marketplace/users/{hidden_trainer_id}/profile",
        json={"role": "trainer", "is_visible": False, "looking_for_trainer": False},
    )

    trainers_response = client.get("/api/v1/marketplace/trainers")
    assert trainers_response.status_code == 200
    trainer_ids = {item["user_id"] for item in trainers_response.json()}
    assert visible_trainer_id in trainer_ids
    assert hidden_trainer_id not in trainer_ids


def test_list_trainers_supports_pagination_and_search() -> None:
    token = f"trainer_page_{uuid4().hex}"
    trainer_a = f"{token}_a"
    trainer_b = f"{token}_b"
    client.put(
        f"/api/v1/marketplace/users/{trainer_a}/profile",
        json={"role": "trainer", "is_visible": True, "looking_for_trainer": False},
    )
    client.put(
        f"/api/v1/marketplace/users/{trainer_b}/profile",
        json={"role": "trainer", "is_visible": True, "looking_for_trainer": False},
    )

    response = client.get(f"/api/v1/marketplace/trainers?page=1&page_size=1&search={token}")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["user_id"] in {trainer_a, trainer_b}
    assert response.headers["x-total-count"] == "2"
    assert response.headers["x-page"] == "1"
    assert response.headers["x-page-size"] == "1"


def test_get_trainer_publication_status() -> None:
    trainer_id = f"trainer_publication_status_{uuid4().hex}"
    client.put(
        f"/api/v1/marketplace/users/{trainer_id}/profile",
        json={"role": "trainer", "is_visible": False, "looking_for_trainer": False},
    )

    hidden_response = client.get(f"/api/v1/marketplace/trainers/{trainer_id}/publication-status")
    assert hidden_response.status_code == 200
    assert hidden_response.json() == {"trainer_user_id": trainer_id, "is_published": False}

    client.put(
        f"/api/v1/marketplace/users/{trainer_id}/profile",
        json={"role": "trainer", "is_visible": True, "looking_for_trainer": False},
    )

    published_response = client.get(f"/api/v1/marketplace/trainers/{trainer_id}/publication-status")
    assert published_response.status_code == 200
    assert published_response.json() == {"trainer_user_id": trainer_id, "is_published": True}

    missing_response = client.get("/api/v1/marketplace/trainers/missing_trainer/publication-status")
    assert missing_response.status_code == 200
    assert missing_response.json() == {"trainer_user_id": "missing_trainer", "is_published": False}


def test_create_accept_leave_relation_flow() -> None:
    client.put(
        "/api/v1/marketplace/users/trainer_2/profile",
        json={"role": "trainer", "is_visible": True, "looking_for_trainer": False},
    )
    client.put(
        "/api/v1/marketplace/users/client_2/profile",
        json={"role": "client", "is_visible": True, "looking_for_trainer": True},
    )

    create_response = client.post(
        "/api/v1/marketplace/relations",
        headers=auth_as("trainer_2"),
        json={
            "trainer_user_id": "trainer_2",
            "client_user_id": "client_2",
            "mode": "invite",
        },
    )
    assert create_response.status_code == 201
    relation = create_response.json()
    assert relation["status"] == "invited"
    relation_id = relation["relation_id"]

    accept_response = client.post(
        f"/api/v1/marketplace/relations/{relation_id}/accept",
        headers=auth_as("client_2"),
    )
    assert accept_response.status_code == 200
    assert accept_response.json()["status"] == "active"

    list_response = client.get("/api/v1/marketplace/trainers/trainer_2/clients?status=active")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    leave_response = client.post(
        f"/api/v1/marketplace/relations/{relation_id}/leave",
        headers=auth_as("trainer_2"),
    )
    assert leave_response.status_code == 200
    assert leave_response.json()["status"] == "ended"


def test_invite_requires_trainer_actor() -> None:
    client.put(
        "/api/v1/marketplace/users/trainer_4/profile",
        json={"role": "trainer", "is_visible": True, "looking_for_trainer": False},
    )
    client.put(
        "/api/v1/marketplace/users/client_4/profile",
        json={"role": "client", "is_visible": True, "looking_for_trainer": True},
    )
    response = client.post(
        "/api/v1/marketplace/relations",
        headers=auth_as("client_4"),
        json={
            "trainer_user_id": "trainer_4",
            "client_user_id": "client_4",
            "mode": "invite",
        },
    )
    assert response.status_code == 403


def test_invite_flow_with_incoming_list_and_decline() -> None:
    client.put(
        "/api/v1/marketplace/users/trainer_5/profile",
        json={"role": "trainer", "is_visible": True, "looking_for_trainer": False},
    )
    client.put(
        "/api/v1/marketplace/users/client_5/profile",
        json={"role": "client", "is_visible": True, "looking_for_trainer": True},
    )
    create_response = client.post(
        "/api/v1/marketplace/relations",
        headers=auth_as("trainer_5"),
        json={
            "trainer_user_id": "trainer_5",
            "client_user_id": "client_5",
            "mode": "invite",
        },
    )
    assert create_response.status_code == 201
    relation_id = create_response.json()["relation_id"]

    incoming_response = client.get("/api/v1/marketplace/clients/client_5/invites")
    assert incoming_response.status_code == 200
    incoming = incoming_response.json()
    assert len(incoming) == 1
    assert incoming[0]["relation_id"] == relation_id
    assert incoming[0]["status"] == "invited"

    decline_response = client.post(
        f"/api/v1/marketplace/relations/{relation_id}/leave",
        headers=auth_as("client_5"),
    )
    assert decline_response.status_code == 200
    assert decline_response.json()["status"] == "declined"

    incoming_after_decline = client.get("/api/v1/marketplace/clients/client_5/invites")
    assert incoming_after_decline.status_code == 200
    assert incoming_after_decline.json() == []


def test_recreate_relation_after_leave() -> None:
    client.put(
        "/api/v1/marketplace/users/trainer_6/profile",
        json={"role": "trainer", "is_visible": True, "looking_for_trainer": False},
    )
    client.put(
        "/api/v1/marketplace/users/client_6/profile",
        json={"role": "client", "is_visible": True, "looking_for_trainer": True},
    )
    first = client.post(
        "/api/v1/marketplace/relations",
        headers=auth_as("trainer_6"),
        json={
            "trainer_user_id": "trainer_6",
            "client_user_id": "client_6",
            "mode": "direct",
        },
    )
    assert first.status_code == 201
    relation_id = first.json()["relation_id"]

    leave_response = client.post(
        f"/api/v1/marketplace/relations/{relation_id}/leave",
        headers=auth_as("trainer_6"),
    )
    assert leave_response.status_code == 200
    assert leave_response.json()["status"] == "ended"

    second = client.post(
        "/api/v1/marketplace/relations",
        headers=auth_as("trainer_6"),
        json={
            "trainer_user_id": "trainer_6",
            "client_user_id": "client_6",
            "mode": "direct",
        },
    )
    assert second.status_code == 201
    assert second.json()["relation_id"] == relation_id
    assert second.json()["status"] == "active"


def test_direct_relation_rejected_when_client_has_active_relation_with_other_trainer() -> None:
    client.put(
        "/api/v1/marketplace/users/trainer_10a/profile",
        json={"role": "trainer", "is_visible": True, "looking_for_trainer": False},
    )
    client.put(
        "/api/v1/marketplace/users/trainer_10b/profile",
        json={"role": "trainer", "is_visible": True, "looking_for_trainer": False},
    )
    client.put(
        "/api/v1/marketplace/users/client_10/profile",
        json={"role": "client", "is_visible": True, "looking_for_trainer": True},
    )

    first = client.post(
        "/api/v1/marketplace/relations",
        headers=auth_as("client_10"),
        json={
            "trainer_user_id": "trainer_10a",
            "client_user_id": "client_10",
            "mode": "direct",
        },
    )
    assert first.status_code == 201

    second = client.post(
        "/api/v1/marketplace/relations",
        headers=auth_as("client_10"),
        json={
            "trainer_user_id": "trainer_10b",
            "client_user_id": "client_10",
            "mode": "direct",
        },
    )
    assert second.status_code == 422
    assert second.json()["detail"] == "client already has active relation"


def test_direct_relation_rejected_when_client_already_connected_to_same_trainer() -> None:
    client.put(
        "/api/v1/marketplace/users/trainer_11/profile",
        json={"role": "trainer", "is_visible": True, "looking_for_trainer": False},
    )
    client.put(
        "/api/v1/marketplace/users/client_11/profile",
        json={"role": "client", "is_visible": True, "looking_for_trainer": True},
    )

    first = client.post(
        "/api/v1/marketplace/relations",
        headers=auth_as("client_11"),
        json={
            "trainer_user_id": "trainer_11",
            "client_user_id": "client_11",
            "mode": "direct",
        },
    )
    assert first.status_code == 201

    second = client.post(
        "/api/v1/marketplace/relations",
        headers=auth_as("client_11"),
        json={
            "trainer_user_id": "trainer_11",
            "client_user_id": "client_11",
            "mode": "direct",
        },
    )
    assert second.status_code == 422
    assert second.json()["detail"] == "client already connected to this trainer"


def test_direct_relation_autocreates_client_discovery_profile() -> None:
    trainer_id = f"trainer_auto_client_{uuid4().hex}"
    client_id = f"client_auto_profile_{uuid4().hex}"

    trainer_upsert = client.put(
        f"/api/v1/marketplace/users/{trainer_id}/profile",
        json={"role": "trainer", "is_visible": True, "looking_for_trainer": False},
    )
    assert trainer_upsert.status_code == 200

    relation_response = client.post(
        "/api/v1/marketplace/relations",
        headers=auth_as(client_id),
        json={
            "trainer_user_id": trainer_id,
            "client_user_id": client_id,
            "mode": "direct",
        },
    )
    assert relation_response.status_code == 201
    assert relation_response.json()["status"] == "active"

    profile_check = client.post(
        "/api/v1/marketplace/profiles/check",
        json={"user_id": client_id, "allowed_roles": ["client"]},
    )
    assert profile_check.status_code == 200
    assert profile_check.json() == {"exists": True, "role": "client"}


def test_trainer_closed_statuses_are_separated() -> None:
    client.put(
        "/api/v1/marketplace/users/trainer_7/profile",
        json={"role": "trainer", "is_visible": True, "looking_for_trainer": False},
    )
    client.put(
        "/api/v1/marketplace/users/client_7a/profile",
        json={"role": "client", "is_visible": True, "looking_for_trainer": True},
    )
    client.put(
        "/api/v1/marketplace/users/client_7b/profile",
        json={"role": "client", "is_visible": True, "looking_for_trainer": True},
    )

    invited = client.post(
        "/api/v1/marketplace/relations",
        headers=auth_as("trainer_7"),
        json={
            "trainer_user_id": "trainer_7",
            "client_user_id": "client_7a",
            "mode": "invite",
        },
    )
    assert invited.status_code == 201
    invited_relation_id = invited.json()["relation_id"]

    declined = client.post(
        f"/api/v1/marketplace/relations/{invited_relation_id}/leave",
        headers=auth_as("client_7a"),
    )
    assert declined.status_code == 200
    assert declined.json()["status"] == "declined"

    direct = client.post(
        "/api/v1/marketplace/relations",
        headers=auth_as("trainer_7"),
        json={
            "trainer_user_id": "trainer_7",
            "client_user_id": "client_7b",
            "mode": "direct",
        },
    )
    assert direct.status_code == 201
    direct_relation_id = direct.json()["relation_id"]

    ended = client.post(
        f"/api/v1/marketplace/relations/{direct_relation_id}/leave",
        headers=auth_as("trainer_7"),
    )
    assert ended.status_code == 200
    assert ended.json()["status"] == "ended"

    declined_list = client.get("/api/v1/marketplace/trainers/trainer_7/clients?status=declined")
    assert declined_list.status_code == 200
    assert len(declined_list.json()) == 1
    assert declined_list.json()[0]["client_user_id"] == "client_7a"

    ended_list = client.get("/api/v1/marketplace/trainers/trainer_7/clients?status=ended")
    assert ended_list.status_code == 200
    assert len(ended_list.json()) == 1
    assert ended_list.json()[0]["client_user_id"] == "client_7b"


def test_trainer_clients_support_pagination_search_and_source_filter() -> None:
    trainer_id = f"trainer_page_filter_{uuid4().hex}"
    direct_client_id = f"client_direct_{uuid4().hex}"
    invite_client_id = f"client_invite_{uuid4().hex}"

    client.put(
        f"/api/v1/marketplace/users/{trainer_id}/profile",
        json={"role": "trainer", "is_visible": True, "looking_for_trainer": False},
    )
    client.put(
        f"/api/v1/marketplace/users/{direct_client_id}/profile",
        json={"role": "client", "is_visible": True, "looking_for_trainer": True},
    )
    client.put(
        f"/api/v1/marketplace/users/{invite_client_id}/profile",
        json={"role": "client", "is_visible": True, "looking_for_trainer": True},
    )

    direct_relation = client.post(
        "/api/v1/marketplace/relations",
        headers=auth_as(trainer_id),
        json={
            "trainer_user_id": trainer_id,
            "client_user_id": direct_client_id,
            "mode": "direct",
        },
    )
    assert direct_relation.status_code == 201

    invite_relation = client.post(
        "/api/v1/marketplace/relations",
        headers=auth_as(trainer_id),
        json={
            "trainer_user_id": trainer_id,
            "client_user_id": invite_client_id,
            "mode": "invite",
        },
    )
    assert invite_relation.status_code == 201
    invite_relation_id = invite_relation.json()["relation_id"]

    accept_invite = client.post(
        f"/api/v1/marketplace/relations/{invite_relation_id}/accept",
        headers=auth_as(invite_client_id),
    )
    assert accept_invite.status_code == 200

    response = client.get(
        f"/api/v1/marketplace/trainers/{trainer_id}/clients"
        f"?status=active&page=1&page_size=1&search={invite_client_id}"
    )
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["client_user_id"] == invite_client_id
    assert payload[0]["source"] == "invite"
    assert response.headers["x-total-count"] == "1"
    assert response.headers["x-page"] == "1"
    assert response.headers["x-page-size"] == "1"


def test_trainer_funnel_metrics() -> None:
    client.put(
        "/api/v1/marketplace/users/trainer_8/profile",
        json={"role": "trainer", "is_visible": True, "looking_for_trainer": False},
    )
    for client_id in ("client_8a", "client_8b", "client_8c"):
        client.put(
            f"/api/v1/marketplace/users/{client_id}/profile",
            json={"role": "client", "is_visible": True, "looking_for_trainer": True},
        )

    invited_pending = client.post(
        "/api/v1/marketplace/relations",
        headers=auth_as("trainer_8"),
        json={
            "trainer_user_id": "trainer_8",
            "client_user_id": "client_8a",
            "mode": "invite",
        },
    )
    assert invited_pending.status_code == 201

    invited_declined = client.post(
        "/api/v1/marketplace/relations",
        headers=auth_as("trainer_8"),
        json={
            "trainer_user_id": "trainer_8",
            "client_user_id": "client_8b",
            "mode": "invite",
        },
    )
    assert invited_declined.status_code == 201
    decline_relation_id = invited_declined.json()["relation_id"]
    decline = client.post(
        f"/api/v1/marketplace/relations/{decline_relation_id}/leave",
        headers=auth_as("client_8b"),
    )
    assert decline.status_code == 200
    assert decline.json()["status"] == "declined"

    invited_accepted = client.post(
        "/api/v1/marketplace/relations",
        headers=auth_as("trainer_8"),
        json={
            "trainer_user_id": "trainer_8",
            "client_user_id": "client_8c",
            "mode": "invite",
        },
    )
    assert invited_accepted.status_code == 201
    accept_relation_id = invited_accepted.json()["relation_id"]
    accept = client.post(
        f"/api/v1/marketplace/relations/{accept_relation_id}/accept",
        headers=auth_as("client_8c"),
    )
    assert accept.status_code == 200
    assert accept.json()["status"] == "active"

    funnel_response = client.get("/api/v1/marketplace/trainers/trainer_8/funnel")
    assert funnel_response.status_code == 200
    funnel = funnel_response.json()
    assert funnel["trainer_user_id"] == "trainer_8"
    assert funnel["invites_sent"] == 3
    assert funnel["invites_pending"] == 1
    assert funnel["invites_accepted"] == 1
    assert funnel["invites_declined"] == 1
    assert funnel["active_clients"] == 1
    assert funnel["invite_acceptance_rate"] == 33.3


def test_marketplace_profile_access_check() -> None:
    client.put(
        "/api/v1/marketplace/users/client_3/profile",
        json={"role": "client", "is_visible": True, "looking_for_trainer": True},
    )
    response = client.post(
        "/api/v1/marketplace/profiles/check",
        json={"user_id": "client_3", "allowed_roles": ["client"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["exists"] is True
    assert body["role"] == "client"


def test_get_client_active_relation() -> None:
    client.put(
        "/api/v1/marketplace/users/trainer_9/profile",
        json={"role": "trainer", "is_visible": True, "looking_for_trainer": False},
    )
    client.put(
        "/api/v1/marketplace/users/client_9/profile",
        json={"role": "client", "is_visible": True, "looking_for_trainer": True},
    )
    create_response = client.post(
        "/api/v1/marketplace/relations",
        headers=auth_as("trainer_9"),
        json={
            "trainer_user_id": "trainer_9",
            "client_user_id": "client_9",
            "mode": "direct",
        },
    )
    assert create_response.status_code == 201
    active_relation = client.get("/api/v1/marketplace/clients/client_9/active-relation")
    assert active_relation.status_code == 200
    body = active_relation.json()
    assert body["trainer_user_id"] == "trainer_9"
    assert body["client_user_id"] == "client_9"
    assert body["status"] == "active"


def test_invalid_role_returns_422() -> None:
    response = client.put(
        "/api/v1/marketplace/users/strange/profile",
        json={"role": "manager", "is_visible": True, "looking_for_trainer": False},
    )
    assert response.status_code == 422


def test_relation_write_requires_bearer_token() -> None:
    response = client.post(
        "/api/v1/marketplace/relations",
        json={
            "trainer_user_id": "trainer_acl",
            "client_user_id": "client_acl",
            "mode": "invite",
        },
    )
    assert response.status_code == 401


def test_relation_write_rejects_outsider_actor() -> None:
    trainer_id = f"trainer_acl_{uuid4().hex}"
    client_id = f"client_acl_{uuid4().hex}"
    outsider_id = f"outsider_acl_{uuid4().hex}"
    client.put(
        f"/api/v1/marketplace/users/{trainer_id}/profile",
        json={"role": "trainer", "is_visible": True, "looking_for_trainer": False},
    )
    client.put(
        f"/api/v1/marketplace/users/{client_id}/profile",
        json={"role": "client", "is_visible": True, "looking_for_trainer": True},
    )

    create_response = client.post(
        "/api/v1/marketplace/relations",
        headers=auth_as(outsider_id),
        json={
            "trainer_user_id": trainer_id,
            "client_user_id": client_id,
            "mode": "invite",
        },
    )
    assert create_response.status_code == 403

    invited = client.post(
        "/api/v1/marketplace/relations",
        headers=auth_as(trainer_id),
        json={
            "trainer_user_id": trainer_id,
            "client_user_id": client_id,
            "mode": "invite",
        },
    )
    assert invited.status_code == 201
    relation_id = invited.json()["relation_id"]

    trainer_accept = client.post(
        f"/api/v1/marketplace/relations/{relation_id}/accept",
        headers=auth_as(trainer_id),
    )
    assert trainer_accept.status_code == 403

    outsider_accept = client.post(
        f"/api/v1/marketplace/relations/{relation_id}/accept",
        headers=auth_as(outsider_id),
    )
    assert outsider_accept.status_code == 403

    outsider_leave = client.post(
        f"/api/v1/marketplace/relations/{relation_id}/leave",
        headers=auth_as(outsider_id),
    )
    assert outsider_leave.status_code == 403