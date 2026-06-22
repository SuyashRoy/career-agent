import sys
from pathlib import Path

# Add career-agent/ to path so shared/ is importable when running from this directory
_REPO_ROOT = Path(__file__).parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from livekit.agents import AgentSession, Agent, cli, WorkerOptions
from livekit.plugins import openai, deepgram, silero, cartesia
from agents.intro_agent import IntroAgent
from shared.config import get_groq_api_key

# class InterviewAgent(Agent):
#     def __init__(self):
#         super().__init__(instructions="You are a friendly mock interview "
#                          "assistant. Greet the candidate and "
#                          "ask them to introduce themselves.")

async def entrypoint(ctx):
    session = AgentSession(
        stt=deepgram.STT(),
        llm=openai.LLM(model="llama-3.3-70b-versatile",
                       base_url="https://api.groq.com/openai/v1",
                       api_key=get_groq_api_key()),
        tts=cartesia.TTS(),
        vad=silero.VAD.load(),
        min_endpointing_delay=3.0,
)
    await session.start(agent=IntroAgent(), room=ctx.room)
    await session.say("Hello! Welcome to this mock interview. Let's start with a self-introduction. Could you tell me a little about yourself?")

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))