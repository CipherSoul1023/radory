from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import get_settings


@dataclass
class ClerkOrganization:
    id: str
    name: str
    slug: str


class ClerkProvisioningError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


class ClerkOrganizationClient:
    """Small, server-only wrapper around Clerk's Backend API."""

    base_url = "https://api.clerk.com/v1"

    def __init__(self, *, secret_key: str | None = None, http_client: httpx.Client | None = None):
        self.secret_key = secret_key if secret_key is not None else get_settings().clerk_secret_key
        self.http_client = http_client

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        if not self.secret_key:
            raise ClerkProvisioningError(
                "Clerk organization provisioning is not configured.", status_code=503
            )
        headers = kwargs.pop("headers", {})
        headers.update(
            {
                "Authorization": f"Bearer {self.secret_key}",
                "Content-Type": "application/json",
            }
        )
        try:
            if self.http_client is not None:
                return self.http_client.request(method, path, headers=headers, **kwargs)
            with httpx.Client(base_url=self.base_url, timeout=15) as client:
                return client.request(method, path, headers=headers, **kwargs)
        except httpx.HTTPError as exc:
            raise ClerkProvisioningError("Clerk could not be reached. Please try again.") from exc

    @staticmethod
    def _safe_error(response: httpx.Response) -> str:
        try:
            payload = response.json()
            errors = payload.get("errors", []) if isinstance(payload, dict) else []
            if errors and isinstance(errors[0], dict):
                return str(
                    errors[0].get("long_message")
                    or errors[0].get("message")
                    or errors[0].get("code")
                )
        except (ValueError, TypeError):
            pass
        return "Clerk rejected organization provisioning."

    @staticmethod
    def _organization(payload: dict[str, Any]) -> ClerkOrganization:
        organization_id = payload.get("id")
        name = payload.get("name")
        slug = payload.get("slug")
        if not all(isinstance(value, str) and value for value in (organization_id, name, slug)):
            raise ClerkProvisioningError("Clerk returned an invalid organization response.")
        return ClerkOrganization(id=organization_id, name=name, slug=slug)

    def get_by_slug(self, slug: str, workspace_id: str) -> ClerkOrganization | None:
        response = self._request("GET", f"/organizations/{slug}")
        if response.status_code == 404:
            return None
        if not response.is_success:
            raise ClerkProvisioningError(self._safe_error(response))
        payload = response.json()
        metadata = payload.get("private_metadata", {})
        if not isinstance(metadata, dict) or metadata.get("radory_workspace_id") != workspace_id:
            raise ClerkProvisioningError("The reserved Clerk organization slug is already in use.")
        return self._organization(payload)

    def create_or_find(
        self, *, name: str, slug: str, user_id: str, workspace_id: str
    ) -> ClerkOrganization:
        existing = self.get_by_slug(slug, workspace_id)
        if existing is not None:
            return existing
        response = self._request(
            "POST",
            "/organizations",
            json={
                "name": name,
                "slug": slug,
                "created_by": user_id,
                "max_allowed_memberships": 5,
                "private_metadata": {"radory_workspace_id": workspace_id},
            },
        )
        if response.is_success:
            return self._organization(response.json())
        # A prior request may have succeeded while its response or local DB write failed.
        if response.status_code in {400, 409, 422}:
            recovered = self.get_by_slug(slug, workspace_id)
            if recovered is not None:
                return recovered
        raise ClerkProvisioningError(self._safe_error(response))

    def list_user_organization_ids(self, user_id: str) -> list[str]:
        organization_ids: list[str] = []
        offset = 0
        while True:
            response = self._request(
                "GET",
                f"/users/{user_id}/organization_memberships",
                params={"limit": 100, "offset": offset},
            )
            if not response.is_success:
                raise ClerkProvisioningError(self._safe_error(response))
            payload = response.json()
            data = payload.get("data", []) if isinstance(payload, dict) else []
            for membership in data:
                organization = membership.get("organization", {})
                organization_id = organization.get("id")
                if isinstance(organization_id, str):
                    organization_ids.append(organization_id)
            total_count = payload.get("total_count", len(organization_ids))
            if not data or len(organization_ids) >= total_count:
                return organization_ids
            offset += len(data)


def get_clerk_organization_client() -> ClerkOrganizationClient:
    return ClerkOrganizationClient()
