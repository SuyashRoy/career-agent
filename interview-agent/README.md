# Interview Agent

A voice-powered AI mock interview system built with LiveKit Agents. The agent conducts a structured two-stage interview — self-introduction followed by past experience — with automated stage transitions and a timeout fallback mechanism.

## How It Works

The agent connects to a LiveKit room and conducts a mock interview through voice interaction. The interview follows a defined two-stage flow:

**Stage 1 — Self-Introduction:** The agent greets the candidate and asks them to introduce themselves. It follows up on education, background, and career interests. Once the LLM determines the candidate has given a substantive introduction (typically 2-3 exchanges), it triggers the transition to Stage 2.

**Stage 2 — Past Experience:** The agent asks about projects, internships, and achievements. It probes for impact, challenges, and learnings. After 3-4 exchanges, it wraps up the interview gracefully.

**Transition Logic:** The primary transition is LLM-driven — the model calls a function tool (`transition_to_experience`) when it judges the introduction is complete. A timeout fallback guarantees progression: if the primary trigger hasn't fired after 4 minutes (due to short answers, silence, or edge cases), the system forces the transition via `session.handoff()`.

```
START
  |
  v
SELF_INTRODUCTION
  |
  +------------------+
  |                  |
  LLM triggers       4-min timeout
  function tool       fires fallback
  |                  |
  v                  v
PAST_EXPERIENCE <----+
  |
  v
END (graceful wrap-up)
```

## Tech Stack

- **LiveKit Agents** — real-time voice agent framework
- **Groq (Llama 3.3 70B)** — LLM for conversational reasoning and transition decisions
- **Deepgram** — speech-to-text
- **Cartesia** — text-to-speech
- **Silero VAD** — voice activity detection for turn-taking

## Project Structure

```
interview-agent/
├── agents/
│   ├── intro_agent.py          # IntroAgent: Stage 1 logic + transition tools
│   └── experience_agent.py     # ExperienceAgent: Stage 2 logic
├── prompts/
│   ├── intro_system.py         # System prompt for introduction stage
│   └── experience_system.py    # System prompt for experience stage
├── app.py                      # Entry point: session setup + agent launch
├── .env                        # API keys (not committed)
└── requirements.txt
```

## Setup

### 1. Accounts Required

| Service | Purpose | Sign Up |
|---------|---------|---------|
| LiveKit Cloud | Real-time voice infrastructure | [livekit.io/cloud](https://livekit.io/cloud) |
| Groq | LLM inference (Llama 3.3 70B) | [console.groq.com](https://console.groq.com) |
| Deepgram | Speech-to-text | [deepgram.com](https://deepgram.com) |
| Cartesia | Text-to-speech | [cartesia.ai](https://cartesia.ai) |

### 2. Environment Variables

Create a `.env` file in the project root:

```
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_livekit_api_key
LIVEKIT_API_SECRET=your_livekit_api_secret
GROQ_API_KEY=gsk_...
DEEPGRAM_API_KEY=...
CARTESIA_API_KEY=...
```

### 3. Install Dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 4. Run

```bash
python app.py dev
```

Connect via the LiveKit Cloud console at `cloud.livekit.io` → your project → Agents → Console.

## Design Decisions

**Why Groq + Llama over OpenAI GPT-4o?** Groq provides the lowest-latency inference available, which directly impacts conversational feel in a voice agent. Sub-200ms token generation makes the agent feel responsive rather than laggy. The free tier also eliminates cost concerns during development and evaluation.

**Why function tools for transitions instead of prompt-only?** Relying on the LLM to output a special token or keyword for transitions is fragile — prompt injection, unexpected phrasing, or model drift can break it. Function tools give the LLM a structured action to call, and LiveKit's framework handles the handoff mechanics. The transition either happens cleanly or it doesn't — no parsing ambiguity.

**Why a timeout fallback?** The LLM-driven transition handles the happy path, but production systems need guarantees. If the candidate gives only monosyllabic responses, the LLM may never reach enough confidence to trigger the tool. The 4-minute watchdog ensures the interview always progresses, preventing stuck states.

## Evaluation

| Test Case | User Behavior | Expected Outcome | Status |
|-----------|--------------|-------------------|--------|
| Normal flow | Articulate, full responses | LLM triggers transition after 2-3 exchanges | |
| Short answers | One-word replies | Agent asks follow-ups; transitions via tool or timeout | |
| Silence | No speech for 4 minutes | Timeout fallback fires, moves to experience | |
| Repetition | Same information repeated | Agent moves forward, no duplicate questions | |

## Future Extensions

- **Interview summary generation** — structured output of key points, skills mentioned, and experience level after the session ends
- **Transcript logging** — timestamped JSON log of all utterances for review
- **Scoring rubric** — communication clarity, confidence, and relevance scoring
- **Additional stages** — technical questions, behavioral scenarios, or case study stages