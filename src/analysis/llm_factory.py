import os
import re
from typing import Any, Optional, Union, List
from langchain_core.messages import AIMessage, BaseMessage

from config.settings import settings
from src.utils.logger import logger


class MockChatModel:
    """
    Deterministic Mock ChatModel for offline testing, local demo runs,
    and scenarios where API keys are not supplied.
    Features robust financial lexicon analysis.
    """
    model_name: str = "mock-chat-model"

    def invoke(self, messages: Any, **kwargs: Any) -> AIMessage:
        if isinstance(messages, list):
            prompt_text = " ".join([getattr(m, "content", str(m)) for m in messages])
        else:
            prompt_text = str(messages)

        lower = prompt_text.lower()

        # Comprehensive Financial Bullish Keywords
        bullish_patterns = [
            r"\bjump(s|ed|ing)?\b", r"\bsurg(e|es|ed|ing)\b", r"\brise(s|d)?\b", r"\brising\b",
            r"\bgrowth\b", r"\brally\b", r"\brallies\b", r"\bprofit(s)?\b", r"\bgain(s|ed)?\b",
            r"\boutperform(s|ed)?\b", r"\bbeat(s)?\b", r"\bexpansion\b", r"\bup\s*\d+%",
            r"\bsoar(s|ed|ing)?\b", r"\bhigh(s)?\b", r"\bbuy\b", r"\bdeal(s)?\b", r"\bacqui(re|sition)\b",
            r"\bdisbursement(s)?\b", r"\border\s*win\b", r"\bdividend\b", r"\brecord\b"
        ]

        # Comprehensive Financial Bearish Keywords
        bearish_patterns = [
            r"\bloss(es)?\b", r"\bplung(e|es|ed|ing)?\b", r"\bslump(s|ed|ing)?\b", r"\bdecline(s|d)?\b",
            r"\bfall(s|ing)?\b", r"\bfell\b", r"\bdrop(s|ped)?\b", r"\bdown\s*\d+%",
            r"\bpenalty\b", r"\bfine(d)?\b", r"\bprobe\b", r"\binvestigat(e|ion)\b",
            r"\bdefault(s|ed)?\b", r"\bdowngrade(s|d)?\b", r"\bunderperform\b", r"\bcautious\b",
            r"\bwarn(s|ing|ed)?\b", r"\bfraud\b", r"\bscrutiny\b", r"\bbankrupt\b"
        ]

        is_bullish = any(re.search(p, lower) for p in bullish_patterns)
        is_bearish = any(re.search(p, lower) for p in bearish_patterns)

        if is_bullish and not is_bearish:
            # Extract possible growth metrics for reasoning
            mock_json = (
                '{"sentiment": "BULLISH", "confidence": 0.88, '
                '"reasoning": "Strong operational momentum, volume growth, and favorable financial indicators.", '
                '"key_catalysts": ["Disbursements and revenue expansion", "Operational outperformance"]}'
            )
        elif is_bearish and not is_bullish:
            mock_json = (
                '{"sentiment": "BEARISH", "confidence": 0.82, '
                '"reasoning": "Downside margin pressure, regulatory scrutiny, or operational headwind.", '
                '"key_catalysts": ["Revenue decline", "Margin pressure"]}'
            )
        elif is_bullish and is_bearish:
            mock_json = (
                '{"sentiment": "NEUTRAL", "confidence": 0.65, '
                '"reasoning": "Mixed market signals with balanced growth indicators and cost/margin headwinds.", '
                '"key_catalysts": ["Mixed quarterly performance"]}'
            )
        else:
            mock_json = (
                '{"sentiment": "NEUTRAL", "confidence": 0.60, '
                '"reasoning": "Routine corporate update with no immediate directional catalyst.", '
                '"key_catalysts": ["General market update"]}'
            )

        return AIMessage(content=mock_json)

    async def ainvoke(self, messages: Any, **kwargs: Any) -> AIMessage:
        return self.invoke(messages, **kwargs)


class LLMFactory:
    """
    Factory creating configured LangChain BaseChatModel instances across multiple providers:
    OpenAI, Anthropic, Groq, Ollama, with automatic fallback to MockChatModel.
    """

    @staticmethod
    def get_chat_model(
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None
    ) -> Any:
        """
        Instantiate and return a LangChain Chat Model.
        """
        prov = (provider or settings.DEFAULT_LLM_PROVIDER or "openai").lower()
        model = model_name or settings.DEFAULT_LLM_MODEL or "gpt-4o-mini"
        temp = temperature if temperature is not None else settings.LLM_TEMPERATURE

        try:
            if prov == "openai":
                api_key = settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")
                if not api_key:
                    logger.warning("OPENAI_API_KEY not found. Using MockChatModel with financial NLP engine.")
                    return MockChatModel()
                from langchain_openai import ChatOpenAI
                return ChatOpenAI(model=model, temperature=temp, api_key=api_key)

            elif prov == "anthropic":
                api_key = settings.ANTHROPIC_API_KEY or os.getenv("ANTHROPIC_API_KEY")
                if not api_key:
                    logger.warning("ANTHROPIC_API_KEY not found. Using MockChatModel with financial NLP engine.")
                    return MockChatModel()
                from langchain_anthropic import ChatAnthropic
                return ChatAnthropic(model=model, temperature=temp, api_key=api_key)

            elif prov == "groq":
                api_key = settings.GROQ_API_KEY or os.getenv("GROQ_API_KEY")
                if not api_key:
                    logger.warning("GROQ_API_KEY not found. Using MockChatModel with financial NLP engine.")
                    return MockChatModel()
                from langchain_groq import ChatGroq
                return ChatGroq(model_name=model, temperature=temp, groq_api_key=api_key)

            elif prov == "ollama":
                from langchain_community.chat_models import ChatOllama
                return ChatOllama(model=model, temperature=temp)

            else:
                return MockChatModel()

        except Exception as e:
            logger.warning(f"Failed to initialize LLM provider '{prov}': {e}. Falling back to MockChatModel.")
            return MockChatModel()
