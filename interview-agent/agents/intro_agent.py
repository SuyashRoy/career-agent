from livekit.agents import function_tool, Agent
from prompts.intro_system import INTRO_AGENT_STRING
from agents.experience_agent import ExperienceAgent
import asyncio, time

INTRO_TIMEOUT = 4*60 ### 4 minutes

class IntroAgent(Agent):
    def __init__(self):
        super().__init__(instructions=INTRO_AGENT_STRING)
        self._start = None
        self._done = False
        self._user_spoke = False
        self._ready_to_wrap = False

    async def on_enter(self):
        self._start = time.time()
        asyncio.create_task(self._nudge_timer())
        asyncio.create_task(self._watchdog())
    
    async def _nudge_timer(self):
        await asyncio.sleep(90)  # 1.5 minutes
        if not self._user_spoke and not self._done:
            await self.session.say(
                "Take your time — whenever you're ready, "
                "go ahead and introduce yourself."
            )
    
    async def _watchdog(self):
        await asyncio.sleep(INTRO_TIMEOUT)
        if not self._done:
            self._ready_to_wrap = True
            await self.session.say(
                "We're running close on time for introductions. "
                "Please finish your current thought, and then we'll "
                "move on to discussing your experience."
            )
            await asyncio.sleep(30) ### Hard cutoff grace period, if still here after 30s, force transition
            if not self._done:
                self._done = True
                self.session.update_agent(ExperienceAgent())

    @function_tool
    async def transition_to_experience(self, confirmation: str = "yes"):
        """Call when candidate has completed intro."""
        self._done = True
        self.session.update_agent(ExperienceAgent())
        return "Transitioning to experience stage now."