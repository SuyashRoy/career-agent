import os
from dotenv import load_dotenv
load_dotenv()

from livekit.agents import AgentSession, Agent, cli, WorkerOptions
from livekit.plugins import openai, deepgram, silero, cartesia
from agents.intro_agent import IntroAgent

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
                       api_key=os.getenv("GROQ_API_KEY")),
        tts=cartesia.TTS(),
        vad=silero.VAD.load(),
)
    await session.start(agent=IntroAgent(), room=ctx.room)
    await session.say("Hello! Welcome to this mock interview. Let's start with a self-introduction. Could you tell me a little about yourself?")

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))