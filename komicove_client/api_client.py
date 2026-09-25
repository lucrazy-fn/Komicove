
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import requests

BASE_URL = (os.environ.get("KOMICOVE_API_BASE_URL")
            or os.environ.get("PANEL_API_BASE_URL")
            or "https://panel-api-tr1a.onrender.com").strip().rstrip("/")
_TIMEOUT_SECONDS = (10, 60)


class ApiUnavailableError(Exception):
    pass


class ApiAuthError(Exception):
    pass


class ApiServerError(Exception):
    pass


@dataclass
class AuthResponse:
    token: str
    user_id: str
    username: str
    display_name: str
    is_moderator: bool = False
    role: str = "user"


@dataclass
class PublicationResult:
    publication_id: str
    comic_id: str
    status: str
    risk_level: str
    public_message: str


def register(username: str, password: str, email: str | None = None) -> AuthResponse:
    return _post_auth("/auth/register", {"username": username, "password": password, "email": email})


def login(username: str, password: str, totp_code: str | None=None) -> AuthResponse:
    return _post_auth("/auth/login", {"username": username, "password": password,"totp_code":totp_code})

def setup_2fa(token: str, current_password: str, current_code: str | None=None) -> dict:
    return _request_json("POST","/account/2fa/setup",token=token,
        payload={"current_password":current_password,"current_code":current_code})
def confirm_2fa(token: str, code: str): return _request_json("POST","/account/2fa/confirm",token=token,payload={"code":code})
def disable_2fa(token: str, current_password: str, code: str):
    return _request_json("POST","/account/2fa/disable",token=token,payload={"current_password":current_password,"code":code})
def request_password_recovery(identifier: str):
    return _request_json("POST","/auth/password-recovery/request",payload={"identifier":identifier})
def confirm_password_recovery(code: str,new_password: str):
    return _request_json("POST","/auth/password-recovery/confirm",payload={"token":code,"new_password":new_password})
def resend_email_verification(token: str):
    return _request_json("POST","/account/email/resend",token=token)
def confirm_email(code: str):
    return _request_json("POST","/auth/email/confirm",payload={"token":code})


def logout(token: str) -> None:
    pass
    try:
        requests.post(
            f"{BASE_URL}/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
            timeout=_TIMEOUT_SECONDS,
        )
    except requests.exceptions.RequestException:
        pass


def get_current_user(token: str) -> AuthResponse:
    pass
    data = _request_json(
        "GET", "/auth/me", token=token,
        auth_error="Sessão expirada ou inválida.",
    )
    return AuthResponse(
        token=token,
        user_id=data["id"],
        username=data["username"],
        display_name=data["display_name"],
        is_moderator=bool(data.get("is_moderator", False)),
        role=data.get("role", "user"),
    )


def claim_moderator(token: str, setup_token: str) -> AuthResponse:
    data = _request_json(
        "POST", "/auth/claim-moderator", token=token,
        payload={"setup_token": setup_token},
    )
    return AuthResponse(
        token=token, user_id=data["id"], username=data["username"],
        display_name=data["display_name"], is_moderator=True,
        role=data.get("role", "admin"),
    )


claim_admin = claim_moderator

def update_profile(token: str, display_name: str, email: str | None) -> dict:
    return _request_json("PATCH", "/account/profile", token=token,
        payload={"display_name": display_name, "email": email})

def get_profile(token: str) -> dict:
    return _request_json("GET", "/account/profile", token=token)

def notifications(token: str) -> list[dict]:
    return _request_json("GET", "/account/notifications", token=token)

def mark_notification_read(token: str, notification_id: str) -> None:
    _request_json("POST", f"/account/notifications/{notification_id}/read", token=token)

def sync_library_state(token: str, items: list[dict]) -> list[dict]:
    return _request_json("PUT", "/account/library-state", token=token, payload={"items": items})


def moderation_queue(token: str, include_decided: bool = False) -> list[dict]:
    suffix = "?include_decided=true" if include_decided else ""
    data = _request_json("GET", f"/moderation/queue{suffix}", token=token)
    if not isinstance(data, list):
        raise ApiServerError("O servidor retornou uma fila inválida.")
    return data


def moderate(token: str, record_id: str, decision: str, reason: str) -> dict:
    data = _request_json(
        "POST", f"/moderation/{record_id}/decision", token=token,
        payload={"decision": decision, "reason": reason},
    )
    if not isinstance(data, dict):
        raise ApiServerError("O servidor retornou uma decisão inválida.")
    return data


def discovery() -> list[dict]:
    data = _request_json("GET", "/publications/discovery")
    if not isinstance(data, list):
        raise ApiServerError("O servidor retornou um catálogo inválido.")
    return data


def remove_publication(token: str, publication_id: str) -> None:
    _request_json("DELETE", f"/publications/{publication_id}", token=token)


def my_publications(token: str) -> list[dict]:
    data = _request_json("GET", "/publications/mine", token=token)
    if not isinstance(data, list):
        raise ApiServerError("O servidor retornou uma lista inválida.")
    return data

def create_report(token: str, target_type: str, target_id: str, reason: str, description: str="") -> dict:
    return _request_json("POST","/reports",token=token,payload={"target_type":target_type,
        "target_id":target_id,"reason":reason,"description":description})

def admin_reports(token: str) -> list[dict]:
    return _request_json("GET","/reports/admin",token=token)

def change_password(token: str, current_password: str, new_password: str):
    return _request_json("POST","/account/password",token=token,
        payload={"current_password":current_password,"new_password":new_password})


def submit_publication(
    token: str, *, title: str, author: str, description: str, tags: list[str],
    file_reference: str, authorship_declared: bool = False,
    authorization_declared: bool = False, license: str | None = None,
    series_title: str | None = None, chapter_number: int | None = None,
) -> PublicationResult:
    pass
    data = _request_json(
        "POST", "/publications", token=token,
        auth_error="Sua sessão expirou. Entre novamente para publicar.",
        payload={
            "title": title, "author": author, "description": description,
            "tags": tags, "file_reference": file_reference,
            "authorship_declared": authorship_declared,
            "authorization_declared": authorization_declared,
            "license": license,
            "series_title": series_title, "chapter_number": chapter_number,
        },
    )
    try:
        return PublicationResult(
            publication_id=data["publication_id"], comic_id=data["comic_id"],
            status=data["status"], risk_level=data["risk_level"],
            public_message=data["public_message"],
        )
    except (KeyError, TypeError) as exc:
        raise ApiServerError("O servidor retornou uma resposta inválida.") from exc


def upload_publication_file(token: str, publication_id: str, file_path: str) -> dict:
    try:
        with open(file_path, "rb") as source:
            resp = requests.put(
                f"{BASE_URL}/publications/{publication_id}/file",
                files={"file": (os.path.basename(file_path), source, "application/octet-stream")},
                headers={"Authorization": f"Bearer {token}"}, timeout=300,
            )
    except OSError as exc:
        raise ApiServerError(f"Não foi possível abrir o arquivo: {exc}") from exc
    except requests.exceptions.RequestException as exc:
        raise ApiUnavailableError(str(exc)) from exc
    return _response_json(resp, "Não foi possível enviar o arquivo.")


def moderation_cover(token: str, record_id: str) -> bytes:
    return _download_bytes(token, f"/moderation/{record_id}/cover")


def publication_cover(publication_id: str, token: str | None = None) -> bytes:
    return _download_bytes(token, f"/publications/{publication_id}/cover")


def download_publication_file(
    publication_id: str, destination: str, token: str | None = None,
) -> str:
    return _download_to_file(
        token, f"/publications/{publication_id}/content", destination
    )


def download_moderation_file(token: str, record_id: str, destination: str) -> str:
    return _download_to_file(
        token, f"/moderation/{record_id}/file", destination
    )


def _download_to_file(token: str | None, path: str, destination: str) -> str:
    temp = destination + ".part"
    try:
        try:
            with requests.get(
                f"{BASE_URL}{path}",
                headers={"Authorization": f"Bearer {token}"} if token else None,
                timeout=300, stream=True,
            ) as resp:
                if not resp.ok:
                    _raise_response_error(resp, "Não foi possível baixar o arquivo.")
                with open(temp, "wb") as target:
                    for chunk in resp.iter_content(1024 * 1024):
                        if chunk:
                            target.write(chunk)
        except requests.exceptions.RequestException as exc:
            raise ApiUnavailableError(str(exc)) from exc
        os.replace(temp, destination)
    finally:
        if os.path.exists(temp):
            os.remove(temp)
    return destination


def _download_bytes(token: str | None, path: str, timeout: int = 30) -> bytes:
    try:
        resp = requests.get(
            f"{BASE_URL}{path}",
            headers={"Authorization": f"Bearer {token}"} if token else None,
            timeout=timeout,
        )
    except requests.exceptions.RequestException as exc:
        raise ApiUnavailableError(str(exc)) from exc
    if not resp.ok:
        _raise_response_error(resp, "Não foi possível baixar o arquivo.")
    return resp.content


def _post_auth(path: str, payload: dict) -> AuthResponse:
    data = _request_json("POST", path, payload=payload)
    try:
        return AuthResponse(
            token=data["token"],
            user_id=data["user"]["id"],
            username=data["user"]["username"],
            display_name=data["user"]["display_name"],
            is_moderator=bool(data["user"].get("is_moderator", False)),
            role=data["user"].get("role", "user"),
        )
    except (KeyError, TypeError) as exc:
        raise ApiServerError("O servidor retornou uma resposta inválida.") from exc


def _request_json(
    method: str, path: str, *, payload: dict | None = None,
    token: str | None = None, auth_error: str = "Credenciais inválidas.",
) -> Any:
    headers = {"Authorization": f"Bearer {token}"} if token else None
    try:
        resp = requests.request(
            method, f"{BASE_URL}{path}", json=payload,
            headers=headers, timeout=_TIMEOUT_SECONDS,
        )
    except requests.exceptions.RequestException as exc:
        raise ApiUnavailableError(str(exc)) from exc

    if not resp.ok:
        _raise_response_error(resp, auth_error)
    if resp.status_code == 204:
        return None
    return _response_json(resp, "O servidor retornou uma resposta inválida.")


def _response_json(resp: requests.Response, fallback: str) -> Any:
    try:
        data = resp.json()
    except ValueError as exc:
        raise ApiServerError(fallback) from exc
    return data


def _raise_response_error(resp: requests.Response, fallback: str) -> None:
    detail = _error_detail(resp, fallback)
    if resp.status_code in (400, 401, 409, 422):
        raise ApiAuthError(detail)
    raise ApiServerError(detail)


def _error_detail(resp: requests.Response, fallback: str) -> str:
    try:
        detail = resp.json().get("detail")
        if isinstance(detail, list):
            return "; ".join(str(item.get("msg", item)) for item in detail)
        if detail:
            return str(detail)
    except (ValueError, AttributeError):
        pass
    return fallback
