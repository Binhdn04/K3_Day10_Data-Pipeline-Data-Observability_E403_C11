from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pipelines.phase1 as phase1


def test_agent_demo_runs_one_question_per_type_and_writes_artifact(monkeypatch) -> None:
    settings = SimpleNamespace(
        llm_provider="test-provider",
        model_name="test-model",
        paths=SimpleNamespace(demo_answers=Path("agent-demo.json")),
    )
    test_set = [
        {"id": "summary-1", "question_type": "summary", "question": "Q1"},
        {"id": "summary-2", "question_type": "summary", "question": "Q2"},
        {"id": "authors-1", "question_type": "authors", "question": "Q3"},
    ]
    written = []
    monkeypatch.setattr(phase1, "build_agent", lambda settings, index: "agent")
    monkeypatch.setattr(phase1, "run_agent_question", lambda agent, question: f"answer:{question}")
    monkeypatch.setattr(phase1, "write_json", lambda path, payload: written.append((path, payload)))

    result = phase1._run_agent_demo(settings, "index", test_set)

    assert result["status"] == "completed"
    assert [item["id"] for item in result["answers"]] == ["summary-1", "authors-1"]
    assert written == [(settings.paths.demo_answers, result)]
