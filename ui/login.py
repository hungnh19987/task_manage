"""Đăng nhập và lấy người dùng hiện tại từ session."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import extra_streamlit_components as stx
import streamlit as st

import config
from core import auth

SESSION_KEY = "user"
COOKIE_NAME = "task_manager_auth"
COOKIE_MANAGER_KEY = "task_manager_cookie_manager"
COOKIE_TTL_DAYS = 30


def create_cookie_manager():
    return stx.CookieManager(key=COOKIE_MANAGER_KEY)


def _encode_login_token(user: dict) -> str:
    expires_at = int(time.time()) + COOKIE_TTL_DAYS * 24 * 60 * 60
    payload = json.dumps(
        {"uid": user["id"], "ver": user["auth_version"], "exp": expires_at},
        separators=(",", ":"),
    ).encode("utf-8")
    encoded = base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")
    signature = hmac.new(
        config.get_auth_cookie_secret().encode("utf-8"),
        encoded.encode("ascii"),
        hashlib.sha256,
    ).digest()
    signed = base64.urlsafe_b64encode(signature).rstrip(b"=").decode("ascii")
    return f"{encoded}.{signed}"


def _decode_login_token(token: str) -> Optional[dict]:
    try:
        encoded, supplied_signature = token.split(".", 1)
        expected_signature = hmac.new(
            config.get_auth_cookie_secret().encode("utf-8"),
            encoded.encode("ascii"),
            hashlib.sha256,
        ).digest()
        signature = base64.urlsafe_b64decode(supplied_signature + "=" * (-len(supplied_signature) % 4))
        if not hmac.compare_digest(signature, expected_signature):
            return None
        payload = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        data = json.loads(payload)
        if int(data["exp"]) <= int(time.time()):
            return None
        return {"id": int(data["uid"]), "auth_version": int(data["ver"])}
    except (KeyError, TypeError, ValueError, UnicodeDecodeError):
        return None


def _clear_cookie(manager) -> None:
    manager.delete(COOKIE_NAME)


def current_user(manager=None) -> Optional[dict]:
    """Người dùng đang đăng nhập, đọc lại từ database ở mỗi lần chạy.

    Nhờ vậy khi ADMIN khóa tài khoản hoặc đổi vai trò, hiệu lực có ngay
    mà không cần chờ người đó đăng xuất.
    """
    data = st.session_state.get(SESSION_KEY)
    manager = manager or create_cookie_manager()
    if not data:
        token = manager.get(COOKIE_NAME)
        if not token:
            return None
        try:
            data = _decode_login_token(token)
        except RuntimeError:
            data = None
        if data is None:
            _clear_cookie(manager)
            return None
        st.session_state[SESSION_KEY] = data
    fresh = auth.get_user(data["id"])
    if (
        fresh is None
        or not fresh["is_active"]
        or fresh["auth_version"] != data.get("auth_version")
    ):
        st.session_state.pop(SESSION_KEY, None)
        _clear_cookie(manager)
        return None
    st.session_state[SESSION_KEY] = fresh
    return fresh


def logout(manager=None) -> None:
    st.session_state.pop(SESSION_KEY, None)
    _clear_cookie(manager or create_cookie_manager())


def render_login(manager=None) -> None:
    manager = manager or create_cookie_manager()
    _, middle, _ = st.columns([1, 2, 1])
    with middle:
        st.title(config.APP_TITLE)
        st.caption("Vui lòng đăng nhập để tiếp tục.")
        with st.form("login_form"):
            username = st.text_input("Tên đăng nhập")
            password = st.text_input("Mật khẩu", type="password")
            submitted = st.form_submit_button("Đăng nhập", width="stretch")
        if submitted:
            user = auth.authenticate(username, password)
            if user:
                try:
                    token = _encode_login_token(user)
                except RuntimeError as exc:
                    st.error(str(exc))
                else:
                    expires_at = datetime.now(timezone.utc) + timedelta(days=COOKIE_TTL_DAYS)
                    manager.set(
                        cookie=COOKIE_NAME,
                        val=token,
                        expires_at=expires_at,
                    )
                    st.session_state[SESSION_KEY] = user
                    st.rerun()
            else:
                st.error("Sai tên đăng nhập hoặc mật khẩu, hoặc tài khoản đã bị khóa.")
