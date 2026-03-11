from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from app.db import LlmProvider, ProviderModel, async_session

router = APIRouter(prefix="/providers", tags=["providers"])


class ModelIn(BaseModel):
    id: str


class ModelItem(BaseModel):
    id: str
    label: str
    provider_id: str


class ProviderOut(BaseModel):
    name: str
    api_base: str | None
    models: list[ModelItem]


class ProviderIn(BaseModel):
    name: str
    api_key: str
    api_base: str | None = None
    models: list[ModelIn] = []


class ProviderUpdateIn(BaseModel):
    api_key: str | None = None
    api_base: str | None = None
    models: list[ModelIn] = []


def _label(model_id: str) -> str:
    return model_id.split("/")[-1]


def _provider_out(row: LlmProvider) -> ProviderOut:
    return ProviderOut(
        name=row.name,
        api_base=row.api_base,
        models=[
            ModelItem(id=pm.model_id, label=_label(pm.model_id), provider_id=row.id)
            for pm in row.models
        ],
    )


def _with_models():
    return select(LlmProvider).options(selectinload(LlmProvider.models))


@router.get("", response_model=list[ProviderOut])
async def list_providers() -> list[ProviderOut]:
    async with async_session() as db:
        rows = await db.scalars(
            _with_models().where(LlmProvider.enabled == True)  # noqa: E712
        )
        return [_provider_out(row) for row in rows]


@router.post("", response_model=ProviderOut, status_code=201)
async def create_provider(body: ProviderIn) -> ProviderOut:
    async with async_session() as db:
        existing = await db.scalar(select(LlmProvider).where(LlmProvider.name == body.name))
        if existing:
            raise HTTPException(status_code=409, detail=f"Provider '{body.name}' already exists")
        row = LlmProvider(
            name=body.name,
            api_key=body.api_key,
            api_base=body.api_base,
            enabled=True,
        )
        db.add(row)
        await db.flush()
        for m in body.models:
            db.add(ProviderModel(provider_id=row.id, model_id=m.id))
        await db.commit()
        provider_name = row.name

    async with async_session() as db:
        result = await db.scalar(_with_models().where(LlmProvider.name == provider_name))
        return _provider_out(result)


@router.put("/{name}", response_model=ProviderOut)
async def update_provider(name: str, body: ProviderUpdateIn) -> ProviderOut:
    async with async_session() as db:
        row = await db.scalar(_with_models().where(LlmProvider.name == name))
        if not row:
            raise HTTPException(status_code=404, detail=f"Provider '{name}' not found")
        if body.api_key is not None and body.api_key != "":
            row.api_key = body.api_key
        row.api_base = body.api_base
        provider_id = row.id

        for pm in list(row.models):
            await db.delete(pm)
        await db.flush()
        for m in body.models:
            db.add(ProviderModel(provider_id=provider_id, model_id=m.id))
        await db.commit()

    async with async_session() as db:
        result = await db.scalar(_with_models().where(LlmProvider.name == name))
        return _provider_out(result)


@router.delete("/{name}", status_code=204)
async def delete_provider(name: str) -> None:
    async with async_session() as db:
        row = await db.scalar(select(LlmProvider).where(LlmProvider.name == name))
        if not row:
            raise HTTPException(status_code=404, detail=f"Provider '{name}' not found")
        await db.execute(delete(LlmProvider).where(LlmProvider.name == name))
        await db.commit()
