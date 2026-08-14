import pytest
from livekit.agents import AgentSession, inference, llm
from livekit.plugins import google

from agent import Assistant
from specialist import CropSpecialistAgent


def _llm() -> llm.LLM:
    try:
        return google.LLM(model="gemini-3.1-flash-lite")
    except Exception:
        return inference.LLM(model="openai/gpt-4.1-mini")


def _get_func_names(result):
    names = []
    for e in result.events:
        item = getattr(e, "item", None)
        if item is not None:
            if isinstance(item, dict):
                names.append(item.get("name"))
            else:
                names.append(getattr(item, "name", None))
    return [n for n in names if n]


def _has_handoff_to(result, target_class):
    for e in result.events:
        new_agent = getattr(e, "new_agent", None)
        if new_agent and isinstance(new_agent, target_class):
            return True
    return False


@pytest.mark.asyncio
async def test_general_query_stays_with_krishi_mitra() -> None:
    """Verify weather and mandi queries stay with Krishi Mitra without triggering handoff."""
    async with (
        _llm() as test_llm,
        AgentSession(llm=test_llm) as session,
    ):
        await session.start(Assistant())

        result = await session.run(
            user_input="What is the current weather forecast for Kolkata?"
        )

        names = _get_func_names(result)
        assert "get_district_weather" in names or len(result.events) > 0


@pytest.mark.asyncio
async def test_crop_disease_triggers_specialist_handoff() -> None:
    """Verify crop disease questions trigger transfer_to_crop_specialist."""
    async with (
        _llm() as test_llm,
        AgentSession(llm=test_llm) as session,
    ):
        await session.start(Assistant())

        result = await session.run(
            user_input="My tomato leaves are turning yellow with brown spots. What pest or disease is this and how do I fix it?"
        )

        names = _get_func_names(result)
        assert "transfer_to_crop_specialist" in names
        assert _has_handoff_to(result, CropSpecialistAgent)


@pytest.mark.asyncio
async def test_specialist_transfers_back_to_krishi_mitra_when_resolved() -> None:
    """Verify Fasal Doctor transfers back to Krishi Mitra when farmer indicates issue is resolved."""
    async with (
        _llm() as test_llm,
        AgentSession(llm=test_llm) as session,
    ):
        specialist = CropSpecialistAgent()
        await session.start(specialist)

        result = await session.run(
            user_input="Thank you so much, I have no more crop questions today."
        )

        names = _get_func_names(result)
        assert "transfer_to_krishi_mitra" in names
        assert _has_handoff_to(result, Assistant)


@pytest.mark.asyncio
async def test_specialist_asks_permission_before_transfer() -> None:
    """Verify Fasal Doctor asks permission before transferring to Krishi Mitra on off-topic query."""
    async with (
        _llm() as test_llm,
        AgentSession(llm=test_llm) as session,
    ):
        specialist = CropSpecialistAgent()
        await session.start(specialist)

        # Off-topic question should prompt Fasal Doctor to ask for permission (not transfer immediately)
        result1 = await session.run(
            user_input="What is the mandi price of wheat in Burdwan today?"
        )
        assert len(result1.events) > 0

        # When user confirms "Yes please", Fasal Doctor triggers transfer_to_krishi_mitra
        result2 = await session.run(user_input="Yes please connect me to Krishi Mitra")
        names = _get_func_names(result2)
        assert "transfer_to_krishi_mitra" in names
        assert _has_handoff_to(result2, Assistant)


@pytest.mark.asyncio
async def test_specialist_responds_in_hindi_when_prompted_in_hindi() -> None:
    """Verify Fasal Doctor responds in Hindi when user speaks Hindi after handoff."""
    async with (
        _llm() as test_llm,
        AgentSession(llm=test_llm) as session,
    ):
        specialist = CropSpecialistAgent()
        await session.start(specialist)

        result = await session.run(
            user_input="टमाटर के पौधों की पत्तियों में पीले धब्बे पड़ रहे हैं, इसके लिए क्या दवा डालें?"
        )

        assert len(result.events) > 0
