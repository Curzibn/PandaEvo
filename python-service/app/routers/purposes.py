from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select

from app.db import LlmProvider, ProviderModel, PurposeModel, async_session

router = APIRouter(prefix="/purposes", tags=["purposes"])

ALL_PURPOSES = ["chat", "title", "worker"]


class PurposeModelItem(BaseModel):
    provider_id: str
    provider_name: str
    model_id: str
    label: str
    sort_order: int


class PurposeModelIn(BaseModel):
    provider_id: str
    model_id: str


class PurposeUpdateIn(BaseModel):
    models: list[PurposeModelIn]


def _label(model_id: str) -> str:
    return model_id.split("/")[-1]


@router.get("/{purpose}", response_model=list[PurposeModelItem])
async def get_purpose_models(purpose: str) -> list[PurposeModelItem]:
    if purpose not in ALL_PURPOSES:
        raise HTTPException(status_code=400, detail=f"Invalid purpose '{purpose}'")
    async with async_session() as db:
        rows = await db.execute(
            select(PurposeModel, LlmProvider)
            .join(LlmProvider, LlmProvider.id == PurposeModel.provider_id)
            .where(PurposeModel.purpose == purpose)
            .order_by(PurposeModel.sort_order)
        )
        return [
            PurposeModelItem(
                provider_id=pm.provider_id,
                provider_name=lp.name,
                model_id=pm.model_id,
                label=_label(pm.model_id),
                sort_order=pm.sort_order,
            )
            for pm, lp in rows.all()
        ]


@router.put("/{purpose}", response_model=list[PurposeModelItem])
async def set_purpose_models(purpose: str, body: PurposeUpdateIn) -> list[PurposeModelItem]:
    if purpose not in ALL_PURPOSES:
        raise HTTPException(status_code=400, detail=f"Invalid purpose '{purpose}'")
    async with async_session() as db:
        for item in body.models:
            exists = await db.scalar(
                select(ProviderModel)
                .where(ProviderModel.provider_id == item.provider_id)
                .where(ProviderModel.model_id == item.model_id)
            )
            if not exists:
                raise HTTPException(
                    status_code=400,
                    detail=f"Model '{item.model_id}' not found in provider '{item.provider_id}'",
                )

        await db.execute(delete(PurposeModel).where(PurposeModel.purpose == purpose))

        for i, item in enumerate(body.models):
            db.add(PurposeModel(
                purpose=purpose,
                provider_id=item.provider_id,
                model_id=item.model_id,
                sort_order=i,
            ))

        await db.commit()

        rows = await db.execute(
            select(PurposeModel, LlmProvider)
            .join(LlmProvider, LlmProvider.id == PurposeModel.provider_id)
            .where(PurposeModel.purpose == purpose)
            .order_by(PurposeModel.sort_order)
        )
        return [
            PurposeModelItem(
                provider_id=pm.provider_id,
                provider_name=lp.name,
                model_id=pm.model_id,
                label=_label(pm.model_id),
                sort_order=pm.sort_order,
            )
            for pm, lp in rows.all()
        ]
