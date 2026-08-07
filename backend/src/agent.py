import json
import logging
import re
from typing import AsyncIterable

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    cli,
    inference,
    tokenize,
    room_io,
)
from livekit.agents.voice.agent import ModelSettings
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")

load_dotenv(".env.local")

# Farm & Field Track: Agricultural Voice Assistant for Indian Farmers (Krishi Mitra)
SYSTEM_PROMPT = """You are Krishi Mitra, a friendly, knowledgeable, and practical agricultural voice assistant for Indian farmers.

CRITICAL OUTPUT FORMAT REQUIREMENT:
You MUST ALWAYS respond ONLY with a valid JSON object containing exactly two keys: "tts_text" and "display_text". Do not include any extra commentary or markdown code fences.

JSON Structure:
{
  "tts_text": "<Pure Devanagari Hindi text for accurate voice synthesis, e.g. 'नमस्ते! मैं आपकी फसल में कैसे मदद कर सकता हूँ?'>",
  "display_text": "<Natural Hinglish text in English alphabet for screen display, e.g. 'Namaste! Main aapki fasal me kaise madad kar sakta hoon?'>"
}

Language & Script Rules:
1. "tts_text": MUST BE IN PURE DEVANAGARI HINDI SCRIPT (Devanagari text guarantees authentic, natural Hindi pronunciation from the text-to-speech engine without English phonetic mispronunciations).
2. "display_text": MUST BE IN NATURAL HINGLISH (Hindi words written in the English/Latin alphabet, easy to read on mobile screens).
3. If the user speaks in English: Set BOTH "tts_text" and "display_text" to clear English text.
4. If the user explicitly asks for pure Hindi on screen: Set BOTH "tts_text" and "display_text" to pure Devanagari Hindi text.

Your goal is to provide concise, easy-to-understand advice on crop management, soil health, pest control, weather precautions, seasonal farming practices, and government agricultural schemes like PM-Kisan. Keep responses brief, natural, clear, and encouraging. Do not use markdown formatting, bullet points, emojis, or complex symbols inside the JSON strings since they will be read out loud."""


def parse_llm_json(raw_text: str) -> tuple[str, str]:
    """Parse JSON output from LLM, returning (tts_text, display_text) with fallback error handling."""
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            tts = data.get("tts_text", raw_text)
            display = data.get("display_text", raw_text)
            return str(tts), str(display)
    except Exception as e:
        logger.warning(f"Failed to parse LLM JSON response: {e}. Falling back to raw text.")
    return raw_text, raw_text


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(instructions=SYSTEM_PROMPT)

    async def tts_node(
        self, text: AsyncIterable[str], model_settings: ModelSettings
    ):
        """Route pure Devanagari Hindi text (tts_text) to Murf Falcon TTS engine."""
        full_text = ""
        async for chunk in text:
            full_text += chunk

        tts_text, _ = parse_llm_json(full_text)

        async def _tts_stream():
            yield tts_text

        async for frame in Agent.default.tts_node(self, _tts_stream(), model_settings):
            yield frame

    async def transcription_node(
        self, text: AsyncIterable[str], model_settings: ModelSettings
    ):
        """Route Hinglish text (display_text) to the user UI / transcript stream."""
        full_text = ""
        async for chunk in text:
            if isinstance(chunk, str):
                full_text += chunk
            elif hasattr(chunk, "text"):
                full_text += chunk.text

        _, display_text = parse_llm_json(full_text)

        async def _display_stream():
            yield display_text

        async for item in Agent.default.transcription_node(self, _display_stream(), model_settings):
            yield item


server = AgentServer()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load(
        min_speech_duration=0.2,
        min_silence_duration=2.0,
        prefix_padding_duration=0.5,
    )


server.setup_fnc = prewarm


@server.rtc_session(agent_name="my-agent")
async def my_agent(ctx: JobContext):
    # Logging setup
    # Add any other context you want in all log entries here
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # Set up a voice AI pipeline using Murf Falcon, Gemini, Deepgram, and the LiveKit turn detector
    session = AgentSession(
        # Speech-to-text (STT) is your agent's ears, turning the user's speech into text that the LLM can understand
        # See all available models at https://docs.livekit.io/agents/models/stt/
        stt=deepgram.STT(
            model="nova-3",
            language="multi",
            endpointing_ms=500,
            smart_format=True,
        ),
        # A Large Language Model (LLM) is your agent's brain, processing user input and generating a response
        # See all available models at https://docs.livekit.io/agents/models/llm/
        llm=google.LLM(
            model="gemini-3.1-flash-lite",
        ),
        # Text-to-speech (TTS) is your agent's voice, turning the LLM's text into speech that the user can hear
        # See all available models as well as voice selections at https://docs.livekit.io/agents/models/tts/
        tts=murf.TTS(
            voice="Anisha", 
            style="Conversation",
            tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
            text_pacing=True
        ),
        # VAD and turn detection are used to determine when the user is speaking and when the agent should respond
        # See more at https://docs.livekit.io/agents/build/turns
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        # allow the LLM to generate a response while waiting for the end of turn
        # See more at https://docs.livekit.io/agents/build/audio/#preemptive-generation
        preemptive_generation=True,
    )

    # To use a realtime model instead of a voice pipeline, use the following session setup instead.
    # (Note: This is for the OpenAI Realtime API. For other providers, see https://docs.livekit.io/agents/models/realtime/))
    # 1. Install livekit-agents[openai]
    # 2. Set OPENAI_API_KEY in .env.local
    # 3. Add `from livekit.plugins import openai` to the top of this file
    # 4. Use the following session setup instead of the version above
    # session = AgentSession(
    #     llm=openai.realtime.RealtimeModel(voice="marin")
    # )

    # # Add a virtual avatar to the session, if desired
    # # For other providers, see https://docs.livekit.io/agents/models/avatar/
    # avatar = hedra.AvatarSession(
    #   avatar_id="...",  # See https://docs.livekit.io/agents/models/avatar/plugins/hedra
    # )
    # # Start the avatar and wait for it to join
    # await avatar.start(session, room=ctx.room)

    # Start the session, which initializes the voice pipeline and warms up the models
    await session.start(
        agent=Assistant(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params: (
                    noise_cancellation.BVCTelephony()
                    if params.participant.kind
                    == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
                    else noise_cancellation.BVC()
                ),
            ),
        ),
    )

    # Join the room and connect to the user
    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(server)
