from __future__ import annotations

import pytest

from gigabacklog_agent import cli


def test_main_uses_offline_mode_when_live_opt_in_is_absent(monkeypatch) -> None:
    observed: list[object] = []

    def fake_run_cli(session, *, input_stream, output_stream):
        observed.append(session)
        return type("Result", (), {"terminal_status": cli.TerminalStatus.COMPLETED})()

    monkeypatch.delenv("GIGACHAT_LIVE", raising=False)
    monkeypatch.setattr(cli, "run_cli", fake_run_cli)
    monkeypatch.setattr(
        cli,
        "create_live_processing_session",
        lambda _: (_ for _ in ()).throw(AssertionError("Live mode must stay opt-in")),
    )

    cli.main()

    assert len(observed) == 1


def test_main_rejects_live_mode_without_credentials_safely(monkeypatch, capsys) -> None:
    monkeypatch.setenv("GIGACHAT_LIVE", "1")
    monkeypatch.delenv("GIGACHAT_CREDENTIALS", raising=False)

    with pytest.raises(SystemExit, match="1"):
        cli.main()

    assert "Не удалось настроить GigaChat" in capsys.readouterr().err
