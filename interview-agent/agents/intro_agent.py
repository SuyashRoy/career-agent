from livekit.agents import function_tool, AgentTransferResult, Agent
from prompts.intro_system import INTRO_AGENT_STRING
from agents.experience_agent import ExperienceAgent
import asyncio, time

INTRO_TIMEOUT = 4*60 ### 4 minutes

class IntroAgent(Agent):
    def __init__(self):
        super().__init__(instructions=INTRO_AGENT_STRING)
        self._start = None
        self._done = False

    async def on_enter(self):
        self._start = time.time()
        asyncio.create_task(self._watchdog())
    
    async def _watchdog(self):
        await asyncio.sleep(INTRO_TIMEOUT)
        if not self._done:
            self._done = True
            await self.session.handoff(
                agent=ExperienceAgent(), 
                summary="Intro timeout. Moving to experience stage."
                )

    @function_tool
    async def transition_to_experience(self):
        """Call when candidate has completed intro."""
        self._done = True
        return AgentTransferResult(
            agent=ExperienceAgent(), 
            summary="Intro complete. Move to experience.")