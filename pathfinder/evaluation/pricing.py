"""Helpers for known model pricing and evaluation-time token costs."""

from __future__ import annotations

from pathfinder.evaluation.models import ModelProfile, PricingConfig
from pathfinder.llm.models import LLMInvocationRecord, LLMProvider


KNOWN_MODEL_PROFILES: dict[tuple[LLMProvider, str], ModelProfile] = {
    (
        LLMProvider.MINIMAX,
        "MiniMax-M2.5",
    ): ModelProfile(
        provider=LLMProvider.MINIMAX,
        model="MiniMax-M2.5",
        total_context_tokens=196_600,
        max_output_tokens=196_600,
        pricing=PricingConfig(
            input_token_price_per_1m_usd=0.30,
            output_token_price_per_1m_usd=1.20,
        ),
    ),
}


def resolve_known_model_profile(provider: LLMProvider, model: str) -> ModelProfile | None:
    return KNOWN_MODEL_PROFILES.get((provider, model))


def resolve_effective_pricing(provider: LLMProvider, model: str, explicit_pricing: PricingConfig | None) -> PricingConfig | None:
    if explicit_pricing is not None:
        return explicit_pricing
    profile = resolve_known_model_profile(provider, model)
    if profile is None:
        return None
    return profile.pricing


def estimate_invocation_cost(invocation: LLMInvocationRecord | None, pricing: PricingConfig | None) -> float | None:
    if invocation is None or pricing is None or invocation.usage is None:
        return None
    if pricing.input_token_price_per_1m_usd is None or pricing.output_token_price_per_1m_usd is None:
        return None

    input_tokens = invocation.usage.input_tokens
    output_tokens = invocation.usage.output_tokens
    if input_tokens is None or output_tokens is None:
        return None

    estimated = (
        (input_tokens / 1_000_000) * pricing.input_token_price_per_1m_usd
        + (output_tokens / 1_000_000) * pricing.output_token_price_per_1m_usd
    )
    return round(estimated, 8)