import pytest
from fastapi import HTTPException

from src import main


class _FailingGraph:
    def __init__(self, message: str):
        self._message = message

    async def ainvoke(self, *_args, **_kwargs):
        raise RuntimeError(self._message)


@pytest.mark.asyncio
async def test_send_message_returns_fallback_for_workspace_limit(monkeypatch):
    session_id = "session_test_quota"
    monkeypatch.setattr(
        main,
        "graph",
        _FailingGraph(
            "Error code: 400 - You have reached your specified workspace API usage "
            "limits. You will regain access on 2026-03-01 at 00:00 UTC."
        ),
    )
    monkeypatch.setattr(
        main,
        "sessions",
        {
            session_id: {
                "customer_email": "sarah@example.com",
                "customer_first_name": "Sarah",
                "customer_last_name": "Jones",
                "customer_shopify_id": "gid://shopify/Customer/7424155189325",
                "thread_id": session_id,
            }
        },
    )
    monkeypatch.setattr(main.database, "update_preview", lambda *_args, **_kwargs: None)

    resp = await main.send_message(main.MessageRequest(session_id=session_id, message="hello"))

    assert resp.session_id == session_id
    assert resp.agent == "system_unavailable"
    assert resp.intent == "GENERAL"
    assert resp.actions_taken == ["LLM_UNAVAILABLE_WORKSPACE_LIMIT"]
    assert "2026-03-01 at 00:00 UTC" in resp.response


@pytest.mark.asyncio
async def test_send_message_keeps_500_for_non_quota_errors(monkeypatch):
    session_id = "session_test_other_error"
    monkeypatch.setattr(main, "graph", _FailingGraph("some other graph failure"))
    monkeypatch.setattr(
        main,
        "sessions",
        {session_id: {"thread_id": session_id, "customer_email": "", "customer_first_name": "", "customer_last_name": "", "customer_shopify_id": ""}},
    )
    monkeypatch.setattr(main.database, "update_preview", lambda *_args, **_kwargs: None)

    with pytest.raises(HTTPException) as err:
        await main.send_message(main.MessageRequest(session_id=session_id, message="hello"))

    assert err.value.status_code == 500
    assert "Graph execution failed" in str(err.value.detail)
