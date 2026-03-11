from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import LlmProvider, ProviderModel, PurposeModel


class ProviderLike(Protocol):
    name: str
    api_key: str
    api_base: str | None
    models: list


@dataclass
class ResolvedModel:
    model_id: str
    api_key: str
    api_base: str | None


async def get_provider_for_model(db: AsyncSession, model_id: str) -> LlmProvider | None:
    return await db.scalar(
        select(LlmProvider)
        .join(ProviderModel, ProviderModel.provider_id == LlmProvider.id)
        .where(LlmProvider.enabled == True)  # noqa: E712
        .where(ProviderModel.model_id == model_id)
    )


@dataclass
class _ProviderLikeImpl:
    name: str
    api_key: str
    api_base: str | None
    models: list


def resolved_to_provider_like(res: ResolvedModel) -> ProviderLike:
    return _ProviderLikeImpl(name="", api_key=res.api_key, api_base=res.api_base, models=[res.model_id])


async def get_models_for_purpose(db: AsyncSession, purpose: str) -> list[ResolvedModel]:
    rows = await db.execute(
        select(PurposeModel, LlmProvider)
        .join(LlmProvider, LlmProvider.id == PurposeModel.provider_id)
        .where(LlmProvider.enabled == True)  # noqa: E712
        .where(PurposeModel.purpose == purpose)
        .order_by(PurposeModel.sort_order)
    )
    return [
        ResolvedModel(model_id=pm.model_id, api_key=lp.api_key, api_base=lp.api_base)
        for pm, lp in rows.all()
    ]


async def get_model_for_purpose(db: AsyncSession, purpose: str) -> ResolvedModel | None:
    models = await get_models_for_purpose(db, purpose)
    return models[0] if models else None
