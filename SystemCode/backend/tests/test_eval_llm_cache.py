import pytest

from scripts.eval_llm_cache import PendingResponse, ReplayClient, prompt_key


def test_miss_writes_pending_then_hit_returns_response_and_clears_pending(tmp_path) -> None:
    client = ReplayClient(tmp_path)
    with pytest.raises(PendingResponse):
        client.complete(system_prompt="SYS", user_prompt="USER")
    key = prompt_key("SYS", "USER")
    pending = tmp_path / "pending" / f"{key}.txt"
    assert "SYS" in pending.read_text(encoding="utf-8") and "USER" in pending.read_text(encoding="utf-8")

    (tmp_path / "responses").mkdir()
    (tmp_path / "responses" / f"{key}.txt").write_text('{"ok": true}', encoding="utf-8")
    assert client.complete(system_prompt="SYS", user_prompt="USER") == '{"ok": true}'
    assert not pending.exists()
    assert client.history == [("SYS", key), ("SYS", key)]
