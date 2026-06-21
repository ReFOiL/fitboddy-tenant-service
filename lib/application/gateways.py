from __future__ import annotations

import json
from urllib import error, request


class ProfileGateway:
    def __init__(self, profile_service_url: str) -> None:
        self._profile_service_url = profile_service_url.rstrip("/")

    def get_full_names_by_user_ids(self, user_ids: list[str]) -> dict[str, str]:
        if not user_ids:
            return {}
        payload = json.dumps({"user_ids": user_ids}).encode("utf-8")
        req = request.Request(
            f"{self._profile_service_url}/api/v1/profiles/internal/summaries",
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
            full_name = item.get("full_name")
            if isinstance(user_id, str) and isinstance(full_name, str) and full_name.strip():
                result[user_id] = full_name.strip()
        return result
