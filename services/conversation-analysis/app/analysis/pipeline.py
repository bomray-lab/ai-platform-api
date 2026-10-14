from app.analysis.extract import extract_transcript
from app.analysis.judge import judge
from app.analysis.llm import LlmClient
from app.analysis.models import DnaType, Judgment, TranscriptTurn


def analyze(
    my_dna_type: DnaType,
    images: list[bytes],
    llm: LlmClient,
) -> tuple[list[TranscriptTurn], Judgment]:
    turns = extract_transcript(images, llm)
    return turns, judge(my_dna_type, turns, llm)
