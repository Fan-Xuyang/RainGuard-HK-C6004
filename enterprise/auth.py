import os, hashlib, secrets, time, hmac
from fastapi import HTTPException, Request
from sqlalchemy import select
from .db import User, Session


def password_hash(password):
    salt = secrets.token_bytes(16)
    return (
        salt.hex()
        + ":"
        + hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1).hex()
    )


DUMMY_HASH = password_hash(secrets.token_urlsafe(24))


def verify(password, stored):
    try:
        salt, hashed = stored.split(":")
        test = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1
        ).hex()
        return hmac.compare_digest(test, hashed)
    except (ValueError, TypeError):
        return False


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def current(request: Request, s):
    token = request.cookies.get("rg_session", "") or request.headers.get(
        "authorization", ""
    ).removeprefix("Bearer ")
    session = s.get(Session, digest(token)) if token else None
    if not session or session.expires < time.time():
        raise HTTPException(401, "请先登录")
    user = s.get(User, session.user_id)
    if not user or not user.active:
        raise HTTPException(401, "账号已停用")
    return user


def require(user, *roles):
    if user.role not in roles:
        raise HTTPException(403, "此角色无权执行操作")


def bootstrap(factory):
    password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")
    with factory.begin() as s:
        if s.scalar(select(User.id).limit(1)):
            return
        if len(password) < 16:
            raise RuntimeError("首次启动请设置至少16字符的 BOOTSTRAP_ADMIN_PASSWORD")
        s.add(
            User(
                username=os.getenv("BOOTSTRAP_ADMIN_USER", "admin"),
                role="admin",
                password=password_hash(password),
            )
        )
