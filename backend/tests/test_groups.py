from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import Database
from app.models import Block, Message
from app.seed import run_seed
from tests.helpers import ALEX, DANIEL, EMMA, LENA, MARCUS, PRIYA, SOFIA, chat_id, login, messages, send

HIRO = "+15550100007"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


@pytest.fixture
async def alex(client: AsyncClient, database: Database) -> dict[str, str]:
    await run_seed(database)
    return await login(client, ALEX)


async def user_id(client: AsyncClient, headers: dict[str, str]) -> int:
    return (await client.get("/api/v1/users/me", headers=headers)).json()["id"]


async def find_id(client: AsyncClient, headers: dict[str, str], phone: str) -> int:
    return (await client.get("/api/v1/users/search", headers=headers, params={"q": phone})).json()[0]["id"]


async def create(client: AsyncClient, headers: dict[str, str], name: str, member_ids: list[int]) -> Any:
    return await client.post("/api/v1/groups", headers=headers, json={"name": name, "member_ids": member_ids})


async def texts(client: AsyncClient, headers: dict[str, str], conversation_id: int) -> list[str]:
    return [m["text"] for m in (await messages(client, headers, conversation_id))["items"]]


# --- create ------------------------------------------------------------------------------------------


async def test_create_group_makes_creator_admin(client: AsyncClient, alex: dict[str, str]) -> None:
    priya_id, marcus_id = await find_id(client, alex, PRIYA), await find_id(client, alex, MARCUS)

    response = await create(client, alex, "  Test Group  ", [priya_id, marcus_id, priya_id])

    assert response.status_code == 201
    group = response.json()
    assert group["title"] == "Test Group" and group["type"] == "group"
    assert group["my_role"] == "admin" and group["member_count"] == 3
    assert await texts(client, alex, group["id"]) == ["You created the group."]
    priya = await login(client, PRIYA)
    assert await texts(client, priya, group["id"]) == ["Alex Rivera created the group."]


@pytest.mark.parametrize(
    "body",
    [
        {"name": "", "member_ids": [1]},
        {"name": "x" * 33, "member_ids": [1]},
        {"name": "Ok", "member_ids": []},
        {"name": "Ok", "member_ids": [99999]},
    ],
)
async def test_create_group_validation(client: AsyncClient, alex: dict[str, str], body: dict[str, Any]) -> None:
    assert (await client.post("/api/v1/groups", headers=alex, json=body)).status_code == 422


async def test_group_with_only_yourself_is_rejected(client: AsyncClient, alex: dict[str, str]) -> None:
    assert (await create(client, alex, "Solo", [await user_id(client, alex)])).status_code == 422


async def test_group_size_is_capped_at_50(client: AsyncClient, alex: dict[str, str]) -> None:
    response = await create(client, alex, "Huge", list(range(10_000, 10_050)))  # 50 others + me = 51

    assert response.status_code == 422
    assert "at most 50" in response.json()["detail"]


async def test_adding_beyond_50_is_rejected(client: AsyncClient, alex: dict[str, str]) -> None:
    trip = await chat_id(client, alex, "Weekend Trip")  # 5 active members

    response = await client.post(
        f"/api/v1/groups/{trip}/members", headers=alex, json={"user_ids": list(range(10_000, 10_046))}
    )

    assert response.status_code == 422


# --- rename / photo ------------------------------------------------------------------------------------


async def test_admin_renames_group(client: AsyncClient, alex: dict[str, str]) -> None:
    trip = await chat_id(client, alex, "Weekend Trip")

    response = await client.patch(f"/api/v1/groups/{trip}", headers=alex, json={"name": "Cabin 2026"})

    assert response.json()["title"] == "Cabin 2026"
    assert (await texts(client, alex, trip))[-1] == 'You changed the group name to "Cabin 2026".'


async def test_non_admin_cannot_rename(client: AsyncClient, alex: dict[str, str]) -> None:
    priya = await login(client, PRIYA)
    trip = await chat_id(client, priya, "Weekend Trip")

    assert (await client.patch(f"/api/v1/groups/{trip}", headers=priya, json={"name": "Mine"})).status_code == 403


async def test_group_endpoints_reject_dms(client: AsyncClient, alex: dict[str, str]) -> None:
    dm = await chat_id(client, alex, "Marcus Chen")

    assert (await client.patch(f"/api/v1/groups/{dm}", headers=alex, json={"name": "X"})).status_code == 404


async def test_group_photo(client: AsyncClient, alex: dict[str, str]) -> None:
    trip = await chat_id(client, alex, "Weekend Trip")
    priya = await login(client, PRIYA)

    ok = await client.put(f"/api/v1/groups/{trip}/avatar", headers=alex, files={"file": ("g.png", PNG, "image/png")})
    not_admin = await client.put(f"/api/v1/groups/{trip}/avatar", headers=priya, files={"file": ("g.png", PNG, "image/png")})
    bad = await client.put(f"/api/v1/groups/{trip}/avatar", headers=alex, files={"file": ("g.png", b"<svg/>", "image/png")})

    assert ok.json()["avatar_url"].startswith("/media/groups/")
    assert not_admin.status_code == 403
    assert bad.status_code == 415


# --- add / re-add ---------------------------------------------------------------------------------------


async def test_added_member_sees_history_from_being_added(client: AsyncClient, alex: dict[str, str]) -> None:
    trip = await chat_id(client, alex, "Weekend Trip")

    await client.post(f"/api/v1/groups/{trip}/members", headers=alex, json={"user_ids": [await find_id(client, alex, HIRO)]})

    hiro = await login(client, HIRO)
    assert await texts(client, hiro, trip) == ["Alex Rivera added you."]


async def test_adding_existing_member_is_409(client: AsyncClient, alex: dict[str, str]) -> None:
    trip = await chat_id(client, alex, "Weekend Trip")
    priya_id = await find_id(client, alex, PRIYA)

    response = await client.post(f"/api/v1/groups/{trip}/members", headers=alex, json={"user_ids": [priya_id]})

    assert response.status_code == 409


async def test_readded_member_does_not_see_the_gap(client: AsyncClient, alex: dict[str, str]) -> None:
    trip = await chat_id(client, alex, "Weekend Trip")
    daniel_id = await find_id(client, alex, DANIEL)  # removed by the seed
    await send(client, alex, trip, "Said while Daniel was away", "c-grp-0001")

    await client.post(f"/api/v1/groups/{trip}/members", headers=alex, json={"user_ids": [daniel_id]})

    daniel = await login(client, DANIEL)
    seen = await texts(client, daniel, trip)
    assert seen == ["Alex Rivera added you."]
    assert (await client.get(f"/api/v1/conversations/{trip}", headers=daniel)).json()["can_send"] is True


# --- remove / leave ---------------------------------------------------------------------------------------


async def test_removed_member_keeps_readonly_history(client: AsyncClient, alex: dict[str, str]) -> None:
    trip = await chat_id(client, alex, "Weekend Trip")

    assert (await client.delete(f"/api/v1/groups/{trip}/members/{await find_id(client, alex, MARCUS)}", headers=alex)).status_code == 204
    await send(client, alex, trip, "After Marcus left", "c-grp-0002")

    marcus = await login(client, MARCUS)
    detail = await client.get(f"/api/v1/conversations/{trip}", headers=marcus)
    assert detail.status_code == 200 and detail.json()["can_send"] is False
    seen = await texts(client, marcus, trip)
    assert seen[-1] == "Alex Rivera removed you." and "After Marcus left" not in seen
    assert (await send(client, marcus, trip, "hello?", "c-grp-0003")).status_code == 403


async def test_never_member_gets_404(client: AsyncClient, alex: dict[str, str]) -> None:
    trip = await chat_id(client, alex, "Weekend Trip")
    hiro = await login(client, HIRO)

    assert (await client.get(f"/api/v1/conversations/{trip}", headers=hiro)).status_code == 404


async def test_non_admin_cannot_remove_others(client: AsyncClient, alex: dict[str, str]) -> None:
    priya = await login(client, PRIYA)
    trip = await chat_id(client, priya, "Weekend Trip")

    response = await client.delete(f"/api/v1/groups/{trip}/members/{await find_id(client, priya, SOFIA)}", headers=priya)

    assert response.status_code == 403


async def test_member_can_leave(client: AsyncClient, alex: dict[str, str]) -> None:
    priya = await login(client, PRIYA)
    trip = await chat_id(client, priya, "Weekend Trip")

    assert (await client.delete(f"/api/v1/groups/{trip}/members/{await user_id(client, priya)}", headers=priya)).status_code == 204
    assert (await texts(client, alex, trip))[-1] == "Priya Sharma left the group."


async def test_last_admin_cannot_leave_and_nothing_is_written(
    client: AsyncClient, alex: dict[str, str], session: AsyncSession
) -> None:
    trip = await chat_id(client, alex, "Weekend Trip")
    before = await session.scalar(select(func.count()).select_from(Message).where(Message.conversation_id == trip))

    response = await client.delete(f"/api/v1/groups/{trip}/members/{await user_id(client, alex)}", headers=alex)

    assert response.status_code == 409
    assert response.json()["detail"] == "Make someone else an admin first"
    after = await session.scalar(select(func.count()).select_from(Message).where(Message.conversation_id == trip))
    assert after == before  # the system message was rolled back too
    assert (await client.get(f"/api/v1/conversations/{trip}", headers=alex)).json()["can_send"] is True


async def test_leaving_as_the_only_member_works(client: AsyncClient, alex: dict[str, str]) -> None:
    priya = await login(client, PRIYA)
    group = (await create(client, alex, "Tiny", [await user_id(client, priya)])).json()
    await client.delete(f"/api/v1/groups/{group['id']}/members/{await user_id(client, priya)}", headers=priya)

    response = await client.delete(f"/api/v1/groups/{group['id']}/members/{await user_id(client, alex)}", headers=alex)

    assert response.status_code == 204


# --- roles --------------------------------------------------------------------------------------------------


async def test_promote_then_former_last_admin_can_leave(client: AsyncClient, alex: dict[str, str]) -> None:
    trip = await chat_id(client, alex, "Weekend Trip")
    priya_id = await find_id(client, alex, PRIYA)

    promoted = await client.patch(f"/api/v1/groups/{trip}/members/{priya_id}", headers=alex, json={"role": "admin"})

    roles = {m["name"]: m["role"] for m in promoted.json()["members"]}
    assert roles["Priya Sharma"] == "admin"
    assert (await texts(client, alex, trip))[-1] == "You made Priya Sharma an admin."
    assert (await client.delete(f"/api/v1/groups/{trip}/members/{await user_id(client, alex)}", headers=alex)).status_code == 204


async def test_last_admin_cannot_be_demoted(client: AsyncClient, alex: dict[str, str]) -> None:
    trip = await chat_id(client, alex, "Weekend Trip")

    response = await client.patch(f"/api/v1/groups/{trip}/members/{await user_id(client, alex)}", headers=alex, json={"role": "member"})

    assert response.status_code == 409


# --- ticks only count current members ------------------------------------------------------------------------


async def test_removed_member_cannot_hold_a_tick_back(client: AsyncClient, alex: dict[str, str]) -> None:
    trip = await chat_id(client, alex, "Weekend Trip")
    sent = (await send(client, alex, trip, "Everyone read this?", "c-grp-0004")).json()
    for phone in (PRIYA, SOFIA, EMMA):  # everyone reads it except Marcus (never online)
        reader = await login(client, phone)
        await client.post(f"/api/v1/conversations/{trip}/read", headers=reader, json={"up_to_message_id": sent["id"]})

    def status_of(items: list[dict[str, Any]]) -> str:
        return next(m["status"] for m in items if m["id"] == sent["id"])

    assert status_of((await messages(client, alex, trip))["items"]) == "sent"  # Marcus hasn't got it
    await client.delete(f"/api/v1/groups/{trip}/members/{await find_id(client, alex, MARCUS)}", headers=alex)

    assert status_of((await messages(client, alex, trip))["items"]) == "read"


# --- message details --------------------------------------------------------------------------------------------


async def test_message_details_for_sender(client: AsyncClient, alex: dict[str, str]) -> None:
    trip = await chat_id(client, alex, "Weekend Trip")
    sent = (await send(client, alex, trip, "Details please", "c-grp-0005")).json()
    priya = await login(client, PRIYA)
    await client.post(f"/api/v1/conversations/{trip}/read", headers=priya, json={"up_to_message_id": sent["id"]})

    details = (await client.get(f"/api/v1/messages/{sent['id']}/receipts", headers=alex)).json()

    by_name = {r["name"]: r for r in details["recipients"]}
    assert set(by_name) == {"Priya Sharma", "Marcus Chen", "Sofia Rossi", "Emma Larsen"}  # not removed Daniel
    assert by_name["Priya Sharma"]["read_at"] is not None
    assert by_name["Marcus Chen"]["delivered_at"] is None


async def test_message_details_access(client: AsyncClient, alex: dict[str, str]) -> None:
    trip = await chat_id(client, alex, "Weekend Trip")
    sent = (await send(client, alex, trip, "Mine", "c-grp-0006")).json()
    system_message = (await messages(client, alex, trip))["items"][0]["id"]

    assert (await client.get(f"/api/v1/messages/{sent['id']}/receipts", headers=await login(client, PRIYA))).status_code == 403
    assert (await client.get(f"/api/v1/messages/{sent['id']}/receipts", headers=await login(client, HIRO))).status_code == 404
    assert (await client.get(f"/api/v1/messages/{system_message}/receipts", headers=alex)).status_code == 404


async def test_message_details_hide_reads_when_sender_has_receipts_off(client: AsyncClient, alex: dict[str, str]) -> None:
    lena = await login(client, LENA)
    book_club = await chat_id(client, lena, "Book Club")
    sent = (await send(client, lena, book_club, "Anyone there?", "c-grp-0007")).json()
    await client.post(f"/api/v1/conversations/{book_club}/read", headers=alex, json={"up_to_message_id": sent["id"]})

    details = (await client.get(f"/api/v1/messages/{sent['id']}/receipts", headers=lena)).json()

    alex_row = next(r for r in details["recipients"] if r["name"] == "Alex Rivera")
    assert alex_row["delivered_at"] is not None and alex_row["read_at"] is None


# --- blocked members in groups (PLAN 7.2, as Signal does) ------------------------------------------------------


async def test_blocked_users_later_group_messages_are_hidden(
    client: AsyncClient, alex: dict[str, str], session: AsyncSession
) -> None:
    priya = await login(client, PRIYA)
    book_club = await chat_id(client, alex, "Book Club")
    unread_before = next(c for c in (await client.get("/api/v1/conversations", headers=alex)).json() if c["id"] == book_club)["unread_count"]
    session.add(Block(blocker_id=await user_id(client, alex), blocked_id=await user_id(client, priya)))
    await session.commit()

    await send(client, priya, book_club, "Alex won't see this", "c-grp-0008")

    alex_sees = await texts(client, alex, book_club)
    assert "Alex won't see this" not in alex_sees
    assert "This month's pick: Project Hail Mary 📚" in alex_sees  # sent before the block: still visible
    assert "Alex won't see this" in await texts(client, await login(client, LENA), book_club)
    unread_after = next(c for c in (await client.get("/api/v1/conversations", headers=alex)).json() if c["id"] == book_club)["unread_count"]
    assert unread_after == unread_before


async def test_blocked_users_group_changes_are_hidden_from_blocker(
    client: AsyncClient, alex: dict[str, str], session: AsyncSession
) -> None:
    """Signal: "you will not see ... changes to the group name, picture, or settings from this contact"."""
    priya = await login(client, PRIYA)  # admin of Book Club
    book_club = await chat_id(client, alex, "Book Club")
    session.add(Block(blocker_id=await user_id(client, alex), blocked_id=await user_id(client, priya)))
    await session.commit()

    await client.patch(f"/api/v1/groups/{book_club}", headers=priya, json={"name": "Renamed by Priya"})
    await client.put(f"/api/v1/groups/{book_club}/avatar", headers=priya, files={"file": ("g.png", PNG, "image/png")})
    await client.post(f"/api/v1/groups/{book_club}/members", headers=priya, json={"user_ids": [await find_id(client, priya, MARCUS)]})

    alex_sees = await texts(client, alex, book_club)
    lena_sees = await texts(client, await login(client, LENA), book_club)
    for line in ('Priya Sharma changed the group name to "Renamed by Priya".', "Priya Sharma changed the group photo.", "Priya Sharma added Marcus Chen."):
        assert line not in alex_sees
        assert line in lena_sees
