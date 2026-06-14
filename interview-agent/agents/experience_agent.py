from livekit.agents import Agent
from prompts.experience_system import EXPERIENCE_AGENT_STRING

class ExperienceAgent(Agent):
    def __init__(self):
        super().__init__(instructions=EXPERIENCE_AGENT_STRING)
                         