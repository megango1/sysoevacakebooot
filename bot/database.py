import os
from datetime import datetime, timezone, timedelta

from supabase import acreate_client, AsyncClient

ADMIN_ID = 1030723047

_client: AsyncClient | None = None


async def get_client() -> AsyncClient:
    global _client
    if _client is None:
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_SERVICE_KEY"]
        _client = await acreate_client(url, key)
    return _client


async def init_db():
    # Tables are created in Supabase via SQL migration — nothing to do here
    await get_client()


# ── Users ─────────────────────────────────────────────────────────────────────

async def upsert_user(user_id: int, username: str, full_name: str):
    db = await get_client()
    await db.table("users").upsert({
        "user_id": user_id,
        "username": username or "",
        "full_name": full_name or "",
    }, on_conflict="user_id").execute()


async def check_access(user_id: int) -> bool:
    if user_id == ADMIN_ID:
        return True
    db = await get_client()
    res = await db.table("users").select("has_access,access_until").eq("user_id", user_id).maybe_single().execute()
    if not res.data:
        return False
    row = res.data
    if not row.get("has_access"):
        return False
    access_until = row.get("access_until")
    if access_until is None:
        return True
    # Parse ISO timestamp from Supabase
    until_dt = datetime.fromisoformat(access_until.replace("Z", "+00:00"))
    return until_dt > datetime.now(timezone.utc)


async def grant_access(user_id: int, days: int = 30):
    db = await get_client()
    until = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
    await db.table("users").update({
        "has_access": True,
        "access_until": until,
    }).eq("user_id", user_id).execute()


async def revoke_access(user_id: int):
    db = await get_client()
    await db.table("users").update({"has_access": False}).eq("user_id", user_id).execute()


async def get_all_users() -> list[dict]:
    db = await get_client()
    res = await db.table("users").select("*").order("joined_at", desc=True).execute()
    return res.data or []


# ── Sections ──────────────────────────────────────────────────────────────────

async def add_section(
    parent_key: str,
    title: str,
    emoji: str,
    content: str,
    photo_file_id: str | None = None,
    video_file_id: str | None = None,
) -> int:
    db = await get_client()
    # Get next order_index
    res = await db.table("sections").select("order_index").eq("parent_key", parent_key).order("order_index", desc=True).limit(1).execute()
    idx = (res.data[0]["order_index"] + 1) if res.data else 1

    ins = await db.table("sections").insert({
        "parent_key": parent_key,
        "title": title,
        "emoji": emoji,
        "content": content,
        "photo_file_id": photo_file_id,
        "video_file_id": video_file_id,
        "order_index": idx,
        "is_active": True,
    }).execute()
    return ins.data[0]["id"]


async def get_subsections(parent_key: str) -> list[dict]:
    db = await get_client()
    res = await db.table("sections").select("*").eq("parent_key", parent_key).eq("is_active", True).order("order_index").execute()
    return res.data or []


async def get_subsection(section_id: int) -> dict | None:
    db = await get_client()
    res = await db.table("sections").select("*").eq("id", section_id).maybe_single().execute()
    return res.data


async def delete_section(section_id: int) -> bool:
    db = await get_client()
    res = await db.table("sections").delete().eq("id", section_id).execute()
    return len(res.data) > 0


async def get_all_sections() -> list[dict]:
    db = await get_client()
    res = await db.table("sections").select("*").order("parent_key").order("order_index").execute()
    return res.data or []
