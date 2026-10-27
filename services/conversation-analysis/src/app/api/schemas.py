from pydantic import BaseModel

from app.analysis.models import Judgment, TranscriptTurn


class _Transcript(BaseModel):
    transcript: list[TranscriptTurn]


class AnalyzeResponse(Judgment, _Transcript):
    pass
