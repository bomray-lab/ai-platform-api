import asyncio
import json
from typing import get_args

import pytest
from pydantic import ValidationError

from app.analysis.judge import DNA_TYPES, judge
from app.analysis.models import DnaType, Judgment
from tests.fakes import FakeLlm, fixture_turns, judgment, judgment_payload


def test_dna_type_table_covers_every_type() -> None:
    assert set(DNA_TYPES) == set(get_args(DnaType))


def test_judge_returns_model_judgment() -> None:
    llm = FakeLlm({Judgment: judgment()})

    result = asyncio.run(judge("카톡 폭탄러", fixture_turns(), llm))

    assert result == judgment()


def test_judge_sends_my_type_and_transcript_without_images() -> None:
    turns = fixture_turns()
    llm = FakeLlm({Judgment: judgment()})

    asyncio.run(judge("카톡 폭탄러", turns, llm))

    [call] = llm.calls
    assert call.text_format is Judgment
    assert call.images == ()
    assert "카톡 폭탄러" in call.text
    assert json.dumps([turn.model_dump() for turn in turns], ensure_ascii=False) in call.text


def test_judge_drops_evidence_not_in_transcript() -> None:
    evidence = ["“글쎄 그때 연락할게”", "보고 싶어", "다음에  보자"]
    llm = FakeLlm({Judgment: judgment(evidence=evidence)})

    result = asyncio.run(judge("잠수 장인", fixture_turns(), llm))

    assert result.evidence == ["“글쎄 그때 연락할게”", "다음에  보자"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"temperature": "lukewarm"},
        {"anger_level": 101},
        {"anger_level": -1},
        {"fish_pond": "maybe"},
        {"signal": "blue"},
        {"dominance": "both"},
        {"recommended_replies": []},
        {"recommended_replies": ["하나", "둘", "셋"]},
        {"reason": None},
    ],
)
def test_judgment_rejects_out_of_schema_values(overrides: dict) -> None:
    with pytest.raises(ValidationError):
        Judgment.model_validate(judgment_payload(**overrides))
