"""WebSocket tests (PLAN section 3). Synchronous: Starlette's TestClient drives WebSockets.

To assert what a socket received without hanging, `drain` sends a ping and collects every
event up to the pong. Events caused by a REST call are sent before that call returns, so
they're always queued ahead of the pong.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.config import Settings
from app.main import create_app
from app.seed import run_seed
from tests.helpers import ALEX, EMMA, LENA, PRIYA

Event = dict[str, Any]
MAYA = "+15550000001"


@pytest.fixture
def live(tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'ws.db'}",
        uploads_dir=tmp_path / "uploads",
        cors_origins=["http://localhost:3000"],
        demo_bots_enabled=True,
        demo_bot_delay_scale=0,
    )
    app = create_app(settings)
    with TestClient(app) as client:
        portal = client.portal
        assert portal is not None  # set while the client is entered
        portal.call(run_seed, app.state.db)
        portal.call(app.state.demo_bots.load)  # the seed ran after startup
        yield client


def token(client: TestClient, phone: str) -> str:
    response = client.post("/api/v1/auth/otp/verify", json={"phone_number": phone, "code": "123456"})
    return response.json()["token"]


def auth(t: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {t}"}


def chat(client: TestClient, t: str, title: str) -> dict[str, Any]:
    return next(c for c in client.get("/api/v1/conversations", headers=auth(t)).json() if c["title"] == title)


def me(client: TestClient, t: str) -> int:
    return client.get("/api/v1/users/me", headers=auth(t)).json()["id"]


def drain(ws: Any) -> list[Event]:
    ws.send_json({"type": "ping", "payload": {}})
    events: list[Event] = []
    while (event := ws.receive_json())["type"] != "pong":
        events.append(event)
    return events


def wait_for(ws: Any, event_type: str) -> dict[str, Any]:
    """For events produced by background work (disconnect cleanup, bots): block until one arrives."""
    while (event := ws.receive_json())["type"] != event_type:
        pass
    return event["payload"]


def of_type(events: list[Event], event_type: str) -> list[dict[str, Any]]:
    return [e["payload"] for e in events if e["type"] == event_type]


def send(client: TestClient, t: str, conversation_id: int, body: str, client_id: str) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        headers=auth(t),
        json={"client_id": client_id, "body": body},
    )
    assert response.status_code in (200, 201), response.text
    return response.json()


# --- connection and presence ---------------------------------------------------------------


def test_bad_token_is_closed_with_4401(live: TestClient) -> None:
    with live.websocket_connect("/ws?token=not-a-token") as ws, pytest.raises(WebSocketDisconnect) as closed:
        ws.receive_json()

    assert closed.value.code == 4401


def test_presence_online_and_offline(live: TestClient) -> None:
    alex, priya = token(live, ALEX), token(live, PRIYA)
    priya_id = me(live, priya)

    with live.websocket_connect(f"/ws?token={alex}") as alex_ws:
        drain(alex_ws)
        with live.websocket_connect(f"/ws?token={priya}") as priya_ws:
            drain(priya_ws)
            online = of_type(drain(alex_ws), "presence.update")
            assert online == [{"user_id": priya_id, "online": True, "last_seen_at": None}]
            assert chat(live, alex, "Priya Sharma")["other_user_online"] is True
        offline = wait_for(alex_ws, "presence.update")

    assert offline["user_id"] == priya_id and offline["online"] is False
    assert offline["last_seen_at"] is not None


def test_bots_are_always_online(live: TestClient) -> None:
    assert chat(live, token(live, ALEX), "Maya (bot)")["other_user_online"] is True


def test_invalid_frame_gets_error_and_socket_stays_open(live: TestClient) -> None:
    with live.websocket_connect(f"/ws?token={token(live, ALEX)}") as ws:
        drain(ws)
        ws.send_text("not json")
        assert ws.receive_json() == {"type": "error", "payload": {"detail": "Invalid frame"}}
        assert drain(ws) == []  # still answers pings


# --- messages and receipts -------------------------------------------------------------------


def test_new_message_is_pushed_and_marked_delivered(live: TestClient) -> None:
    alex, priya = token(live, ALEX), token(live, PRIYA)
    dm = chat(live, alex, "Priya Sharma")["id"]

    with live.websocket_connect(f"/ws?token={alex}") as alex_ws, live.websocket_connect(f"/ws?token={priya}") as priya_ws:
        drain(alex_ws)
        drain(priya_ws)
        sent = send(live, alex, dm, "Live hello", "ws-test-0001")

        to_priya = of_type(drain(priya_ws), "message.new")
        to_alex = drain(alex_ws)

    assert len(to_priya) == 1
    assert to_priya[0]["message"]["text"] == "Live hello"
    assert to_priya[0]["message"]["sender_name"] == "Alex Rivera"  # worded for Priya
    assert to_priya[0]["message"]["client_id"] is None
    assert of_type(to_alex, "message.new")[0]["message"]["client_id"] == "ws-test-0001"  # my other tabs
    assert of_type(to_alex, "message.status") == [
        {"conversation_id": dm, "updates": [{"message_id": sent["id"], "status": "delivered"}]}
    ]


def test_read_is_pushed_to_sender(live: TestClient) -> None:
    alex, priya = token(live, ALEX), token(live, PRIYA)
    dm = chat(live, alex, "Priya Sharma")["id"]

    with live.websocket_connect(f"/ws?token={alex}") as alex_ws, live.websocket_connect(f"/ws?token={priya}") as priya_ws:
        drain(alex_ws)
        drain(priya_ws)
        sent = send(live, alex, dm, "Read me", "ws-test-0002")
        drain(alex_ws)

        live.post(f"/api/v1/conversations/{dm}/read", headers=auth(priya), json={"up_to_message_id": sent["id"]})

        assert of_type(drain(alex_ws), "message.status") == [
            {"conversation_id": dm, "updates": [{"message_id": sent["id"], "status": "read"}]}
        ]


def test_receipts_off_reader_never_sends_read(live: TestClient) -> None:
    alex, lena = token(live, ALEX), token(live, LENA)
    dm = chat(live, alex, "Lena Fischer")["id"]

    with live.websocket_connect(f"/ws?token={alex}") as alex_ws:
        drain(alex_ws)
        sent = send(live, alex, dm, "Hi Lena", "ws-test-0003")
        assert of_type(drain(alex_ws), "message.status") == []  # Lena isn't connected: still "sent"

        live.post(f"/api/v1/conversations/{dm}/read", headers=auth(lena), json={"up_to_message_id": sent["id"]})

        statuses = of_type(drain(alex_ws), "message.status")
    assert [u["status"] for s in statuses for u in s["updates"]] == ["delivered"]


def test_pending_messages_are_delivered_on_connect(live: TestClient) -> None:
    alex, emma = token(live, ALEX), token(live, EMMA)
    dm = chat(live, alex, "Emma Larsen")["id"]

    with live.websocket_connect(f"/ws?token={alex}") as alex_ws:
        drain(alex_ws)
        sent = send(live, alex, dm, "While you were away", "ws-test-0004")
        drain(alex_ws)

        with live.websocket_connect(f"/ws?token={emma}") as emma_ws:
            drain(emma_ws)
            updates = [u for s in of_type(drain(alex_ws), "message.status") for u in s["updates"]]

    assert {"message_id": sent["id"], "status": "delivered"} in updates


def test_retry_does_not_broadcast_again(live: TestClient) -> None:
    alex, priya = token(live, ALEX), token(live, PRIYA)
    dm = chat(live, alex, "Priya Sharma")["id"]

    with live.websocket_connect(f"/ws?token={priya}") as priya_ws:
        drain(priya_ws)
        send(live, alex, dm, "Once", "ws-test-0005")
        send(live, alex, dm, "Once", "ws-test-0005")

        assert len(of_type(drain(priya_ws), "message.new")) == 1


# --- replies and reactions -------------------------------------------------------------------


def test_reply_quote_is_pushed_worded_for_the_receiver(live: TestClient) -> None:
    alex, priya = token(live, ALEX), token(live, PRIYA)
    dm = chat(live, alex, "Priya Sharma")["id"]
    original = send(live, alex, dm, "Original", "ws-reply-0001")

    with live.websocket_connect(f"/ws?token={priya}") as priya_ws:
        drain(priya_ws)
        response = live.post(
            f"/api/v1/conversations/{dm}/messages",
            headers=auth(priya),
            json={"client_id": "ws-reply-0002", "body": "Answer", "reply_to_id": original["id"]},
        )
        assert response.status_code == 201, response.text
        pushed = of_type(drain(priya_ws), "message.new")

    assert pushed[0]["message"]["quote"] == {"id": original["id"], "sender_id": me(live, alex), "author_name": "Alex Rivera", "text": "Original"}


def test_reaction_updates_are_pushed_to_members(live: TestClient) -> None:
    alex, priya = token(live, ALEX), token(live, PRIYA)
    dm = chat(live, alex, "Priya Sharma")["id"]
    message = send(live, alex, dm, "React to me", "ws-react-0001")
    priya_id = me(live, priya)

    with live.websocket_connect(f"/ws?token={alex}") as alex_ws, live.websocket_connect(f"/ws?token={priya}") as priya_ws:
        drain(alex_ws)
        drain(priya_ws)
        live.put(f"/api/v1/messages/{message['id']}/reaction", headers=auth(priya), json={"emoji": "😂"})
        live.delete(f"/api/v1/messages/{message['id']}/reaction", headers=auth(priya))

        to_alex = of_type(drain(alex_ws), "reaction.updated")
        to_priya = of_type(drain(priya_ws), "reaction.updated")  # her other tabs

    expected = [
        {"conversation_id": dm, "message_id": message["id"], "user_id": priya_id, "emoji": "😂"},
        {"conversation_id": dm, "message_id": message["id"], "user_id": priya_id, "emoji": None},
    ]
    assert to_alex == expected and to_priya == expected


def test_delete_for_everyone_is_pushed_to_members(live: TestClient) -> None:
    alex, priya = token(live, ALEX), token(live, PRIYA)
    dm = chat(live, alex, "Priya Sharma")["id"]
    sent = send(live, alex, dm, "Delete me", "ws-delete-0001")

    with live.websocket_connect(f"/ws?token={alex}") as alex_ws, live.websocket_connect(f"/ws?token={priya}") as priya_ws:
        drain(alex_ws)
        drain(priya_ws)
        assert live.delete(f"/api/v1/messages/{sent['id']}", headers=auth(alex)).status_code == 204

        to_priya = of_type(drain(priya_ws), "message.deleted")
        to_alex = of_type(drain(alex_ws), "message.deleted")  # my other tabs

    assert to_priya == to_alex == [{"conversation_id": dm, "message_id": sent["id"]}]


# --- typing ------------------------------------------------------------------------------------


def test_typing_is_relayed_to_others_only(live: TestClient) -> None:
    alex, priya = token(live, ALEX), token(live, PRIYA)
    dm = chat(live, alex, "Priya Sharma")["id"]
    alex_id = me(live, alex)

    with live.websocket_connect(f"/ws?token={alex}") as alex_ws, live.websocket_connect(f"/ws?token={priya}") as priya_ws:
        drain(alex_ws)
        drain(priya_ws)
        alex_ws.send_json({"type": "typing.start", "payload": {"conversation_id": dm}})
        alex_ws.send_json({"type": "typing.stop", "payload": {"conversation_id": dm}})

        mine = drain(alex_ws)
        theirs = drain(priya_ws)

    their_typing = [e for e in theirs if e["type"].startswith("typing.")]
    assert [e["type"] for e in their_typing] == ["typing.start", "typing.stop"]
    assert their_typing[0]["payload"] == {"conversation_id": dm, "user_id": alex_id}
    # Only typing matters here: Priya's "online" event may land in Alex's batch, depending on timing.
    assert [e for e in mine if e["type"].startswith("typing.")] == []


def test_typing_in_foreign_conversation_is_an_error(live: TestClient) -> None:
    priya = token(live, PRIYA)
    priya_marcus = chat(live, priya, "Marcus Chen")["id"]

    with live.websocket_connect(f"/ws?token={token(live, ALEX)}") as ws:
        drain(ws)
        ws.send_json({"type": "typing.start", "payload": {"conversation_id": priya_marcus}})

        assert drain(ws) == [{"type": "error", "payload": {"detail": "Not a member of this conversation"}}]


# --- demo bots --------------------------------------------------------------------------------------


def test_bot_delivers_reads_types_and_replies(live: TestClient) -> None:
    alex = token(live, ALEX)
    maya_dm = chat(live, alex, "Maya (bot)")

    with live.websocket_connect(f"/ws?token={alex}") as ws:
        drain(ws)
        sent = send(live, alex, maya_dm["id"], "hello", "ws-test-0006")

        seen: list[str] = []
        while True:  # bot work runs in a background task; wait for its reply
            event = ws.receive_json()
            if event["type"] == "message.status":
                seen += [u["status"] for u in event["payload"]["updates"] if u["message_id"] == sent["id"]]
            elif event["type"] in ("typing.start", "typing.stop"):
                seen.append(event["type"])
            elif event["type"] == "message.new" and event["payload"]["message"]["sender_id"] == maya_dm["other_user_id"]:
                reply = event["payload"]["message"]
                break

    assert seen == ["delivered", "read", "typing.start", "typing.stop"]
    assert reply["text"] == "Hey there! 👋"
    assert reply["sender_name"] == "Maya (bot)"


# --- groups ------------------------------------------------------------------------------------------


def test_new_group_reaches_members_live(live: TestClient) -> None:
    alex, priya = token(live, ALEX), token(live, PRIYA)

    with live.websocket_connect(f"/ws?token={priya}") as priya_ws:
        drain(priya_ws)
        group = live.post(
            "/api/v1/groups", headers=auth(alex), json={"name": "Live Group", "member_ids": [me(live, priya)]}
        ).json()
        events = drain(priya_ws)

    assert of_type(events, "message.new")[0]["message"]["text"] == "Alex Rivera created the group."
    assert of_type(events, "group.updated")[0]["conversation_id"] == group["id"]


def test_removed_member_gets_removal_but_nothing_after(live: TestClient) -> None:
    alex, marcus = token(live, ALEX), token(live, "+15550100003")
    trip = chat(live, alex, "Weekend Trip")["id"]
    marcus_id = me(live, marcus)

    with live.websocket_connect(f"/ws?token={marcus}") as marcus_ws:
        drain(marcus_ws)
        live.delete(f"/api/v1/groups/{trip}/members/{marcus_id}", headers=auth(alex))
        removal = drain(marcus_ws)
        send(live, alex, trip, "Marcus shouldn't get this", "ws-test-0101")
        after = drain(marcus_ws)

    assert [m["message"]["text"] for m in of_type(removal, "message.new")] == ["Alex Rivera removed you."]
    assert of_type(removal, "group.updated") == [
        {"conversation_id": trip, "change": "member_removed", "actor_id": me(live, alex), "target_ids": [marcus_id]}
    ]
    assert after == []


# --- privacy settings and blocks ------------------------------------------------------------------------


def test_typing_indicators_off_neither_sends_nor_receives(live: TestClient) -> None:
    alex, priya = token(live, ALEX), token(live, PRIYA)
    dm = chat(live, alex, "Priya Sharma")["id"]
    live.patch("/api/v1/users/me/settings", headers=auth(priya), json={"typing_indicators_enabled": False})

    with live.websocket_connect(f"/ws?token={alex}") as alex_ws, live.websocket_connect(f"/ws?token={priya}") as priya_ws:
        drain(alex_ws)
        drain(priya_ws)
        priya_ws.send_json({"type": "typing.start", "payload": {"conversation_id": dm}})
        alex_ws.send_json({"type": "typing.start", "payload": {"conversation_id": dm}})
        to_priya = drain(priya_ws)
        to_alex = drain(alex_ws)

    assert of_type(to_alex, "typing.start") == []  # Priya's typing isn't sent
    assert of_type(to_priya, "typing.start") == []  # and she doesn't see Alex's


def test_read_receipts_off_sends_no_read_event(live: TestClient) -> None:
    alex, priya = token(live, ALEX), token(live, PRIYA)
    dm = chat(live, alex, "Priya Sharma")["id"]
    live.patch("/api/v1/users/me/settings", headers=auth(priya), json={"read_receipts_enabled": False})

    with live.websocket_connect(f"/ws?token={alex}") as alex_ws, live.websocket_connect(f"/ws?token={priya}") as priya_ws:
        drain(alex_ws)
        drain(priya_ws)
        sent = send(live, alex, dm, "Will you read this?", "ws-test-0201")
        drain(alex_ws)
        live.post(f"/api/v1/conversations/{dm}/read", headers=auth(priya), json={"up_to_message_id": sent["id"]})
        statuses = [u["status"] for s in of_type(drain(alex_ws), "message.status") for u in s["updates"]]

    assert "read" not in statuses


def test_blocked_senders_message_is_not_pushed(live: TestClient) -> None:
    alex, priya = token(live, ALEX), token(live, PRIYA)
    live.put(f"/api/v1/blocks/{me(live, priya)}", headers=auth(alex))
    dm = chat(live, priya, "Alex Rivera")["id"]

    with live.websocket_connect(f"/ws?token={alex}") as alex_ws, live.websocket_connect(f"/ws?token={priya}") as priya_ws:
        drain(alex_ws)
        drain(priya_ws)
        send(live, priya, dm, "Hello?", "ws-test-0202")
        to_alex = drain(alex_ws)
        to_priya = drain(priya_ws)

    assert of_type(to_alex, "message.new") == []
    assert of_type(to_priya, "message.status") == []  # no delivered tick
