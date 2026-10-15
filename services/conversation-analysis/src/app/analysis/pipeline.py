from app.analysis.extract import extract_transcript
from app.analysis.judge import judge
from app.analysis.llm import LlmClient
from app.analysis.models import DnaType, Judgment, TranscriptTurn


async def analyze(
    my_dna_type: DnaType,
    images: list[bytes],
    llm: LlmClient,
) -> tuple[list[TranscriptTurn], Judgment]:
    turns = await extract_transcript(images, llm)
    return turns, await judge(my_dna_type, turns, llm)
