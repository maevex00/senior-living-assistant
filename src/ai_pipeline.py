"""Compatibility imports after the Gemini migration; no duplicate AI implementation."""
from backend.ai import GeminiService
from src.budget import regex_budget_fallback as _regex_budget_fallback

__all__ = ["GeminiService", "_regex_budget_fallback"]
