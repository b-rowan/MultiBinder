from fastapi import APIRouter, HTTPException, Depends, Request, Query, UploadFile, File
from fastapi.responses import HTMLResponse
from tortoise.functions import Count, Sum
from app.models.card import Card, UserCollection
from app.models.collection import Collection
from app.models.user import User
from app.schemas.card import (
    CollectionEntryCreate, CollectionEntryUpdate, CollectionCreate, CollectionUpdate,
)
from app.services.auth import get_current_user
from app.services.moxfield import sync_moxfield_collection
from app.services.manabox import sync_manabox_collection
from datetime import datetime, timezone
import math
import csv
import io

from app.templates import templates

router = APIRouter()


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def _get_or_create_default_collection(user: User) -> Collection:
    coll = await Collection.filter(user=user, type="personal").order_by("created_at").first()
    if not coll:
        coll = await Collection.create(user=user, name="My Collection", type="personal")
    return coll


async def _require_collection(collection_id: int, user: User) -> Collection:
    coll = await Collection.filter(id=collection_id, user=user).first()
    if not coll:
        raise HTTPException(status_code=404, detail="Collection not found")
    return coll


def _serialize_entry(entry, card) -> dict:
    return {
        "id": entry.id,
        "card": {
            "scryfall_id": card.scryfall_id,
            "name": card.name,
            "mana_cost": card.mana_cost,
            "cmc": card.cmc,
            "type_line": card.type_line,
            "oracle_text": card.oracle_text,
            "colors": card.colors,
            "color_identity": card.color_identity,
            "set_code": card.set_code,
            "set_name": card.set_name,
            "collector_number": card.collector_number,
            "rarity": card.rarity,
            "image_uri_small": card.image_uri_small,
            "image_uri_normal": card.image_uri_normal,
            "image_uri_large": card.image_uri_large,
            "power": card.power,
            "toughness": card.toughness,
            "loyalty": card.loyalty,
            "layout": card.layout,
            "card_faces": card.card_faces,
            "legalities": card.legalities,
        },
        "quantity": entry.quantity,
        "finish": entry.finish,
        "added_at": entry.added_at.isoformat() if entry.added_at else None,
    }


# ─── Page ─────────────────────────────────────────────────────────────────────

@router.get("/collection", response_class=HTMLResponse)
async def collection_page(request: Request):
    return templates.TemplateResponse(request, "collection.html")


# ─── Collection CRUD ──────────────────────────────────────────────────────────

@router.get("/api/collections", response_model=list)
async def list_collections(current_user: User = Depends(get_current_user)):
    collections = await (
        Collection.filter(user=current_user)
        .annotate(entry_count=Sum("entries__quantity"), unique_card_count=Count("entries__card__name", distinct=True))
        .order_by("created_at")
    )
    return [
        {
            "id": c.id,
            "name": c.name,
            "description": c.description,
            "type": c.type,
            "external_source": c.external_source,
            "external_url": c.external_url,
            "last_synced": c.last_synced.isoformat() if c.last_synced else None,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "entry_count": c.entry_count or 0,
            "unique_card_count": c.unique_card_count or 0,
        }
        for c in collections
    ]


@router.post("/api/collections", response_model=dict)
async def create_collection(
    data: CollectionCreate,
    current_user: User = Depends(get_current_user),
):
    coll = await Collection.create(
        user=current_user,
        name=data.name,
        description=data.description or "",
        type=data.type,
        external_source=data.external_source,
        external_url=data.external_url,
    )
    return {
        "id": coll.id,
        "name": coll.name,
        "description": coll.description,
        "type": coll.type,
        "external_source": coll.external_source,
        "external_url": coll.external_url,
        "last_synced": None,
        "created_at": coll.created_at.isoformat() if coll.created_at else None,
        "entry_count": 0,
            "unique_card_count": 0,
    }


@router.put("/api/collections/{collection_id}", response_model=dict)
async def update_collection(
    collection_id: int,
    data: CollectionUpdate,
    current_user: User = Depends(get_current_user),
):
    coll = await _require_collection(collection_id, current_user)
    if data.name is not None:
        coll.name = data.name
    if data.description is not None:
        coll.description = data.description
    if data.external_url is not None:
        coll.external_url = data.external_url
    await coll.save()
    return {"id": coll.id, "message": "Updated"}


@router.delete("/api/collections/{collection_id}", response_model=dict)
async def delete_collection(
    collection_id: int,
    current_user: User = Depends(get_current_user),
):
    coll = await _require_collection(collection_id, current_user)
    await coll.delete()
    return {"message": "Collection deleted"}


@router.post("/api/collections/{collection_id}/sync", response_model=dict)
async def sync_collection(
    collection_id: int,
    current_user: User = Depends(get_current_user),
):
    coll = await _require_collection(collection_id, current_user)
    if coll.type != "external":
        raise HTTPException(status_code=400, detail="Only external collections can be synced")
    if not coll.external_source or not coll.external_url:
        raise HTTPException(status_code=400, detail="Collection is missing external_source or external_url")

    if coll.external_source == "moxfield":
        try:
            result = await sync_moxfield_collection(coll)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Sync failed: {e}")
    elif coll.external_source == "manabox":
        try:
            result = await sync_manabox_collection(coll)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Sync failed: {e}")
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported external source: {coll.external_source}")

    coll.last_synced = datetime.now(timezone.utc)
    await coll.save()

    return {
        "message": "Sync complete",
        "source_name": result["source_name"],
        "added": result["added"],
        "not_found": result["not_found"],
    }


# ─── Collection Entries ───────────────────────────────────────────────────────

@router.get("/api/collection", response_model=dict)
async def get_my_collection(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=40, ge=1, le=500),
    q: str = Query(default=""),
    collection_id: int = Query(default=None),
    current_user: User = Depends(get_current_user),
):
    # collection_id=0 means "All Collections" aggregate view
    if collection_id == 0:
        user_collection_ids = await Collection.filter(user=current_user).values_list("id", flat=True)
        if q:
            matching_cards = await Card.filter(name__icontains=q).values_list("scryfall_id", flat=True)
            query = UserCollection.filter(collection_id__in=list(user_collection_ids), card_id__in=list(matching_cards))
        else:
            query = UserCollection.filter(collection_id__in=list(user_collection_ids))

        total = await query.count()
        pages = math.ceil(total / limit) if total > 0 else 1
        offset = (page - 1) * limit

        entries = await query.offset(offset).limit(limit).prefetch_related("card")
        result = [_serialize_entry(e, e.card) for e in entries]

        if total > 0:
            all_entries = await query.values("quantity", "card_id")
            total_quantity = sum(e["quantity"] for e in all_entries)
            unique_card_ids = {e["card_id"] for e in all_entries}
            unique_names_list = await Card.filter(scryfall_id__in=list(unique_card_ids)).values_list("name", flat=True)
            unique_names = len(set(unique_names_list))
        else:
            total_quantity = 0
            unique_names = 0

        return {
            "entries": result,
            "total": total,
            "total_quantity": total_quantity,
            "unique_names": unique_names,
            "page": page,
            "limit": limit,
            "pages": pages,
            "collection_id": 0,
            "collection_name": "All Collections",
            "collection_type": "aggregate",
        }

    if collection_id is not None:
        coll = await _require_collection(collection_id, current_user)
    else:
        coll = await _get_or_create_default_collection(current_user)

    if q:
        matching_cards = await Card.filter(name__icontains=q).values_list("scryfall_id", flat=True)
        query = UserCollection.filter(collection=coll, card_id__in=list(matching_cards))
    else:
        query = UserCollection.filter(collection=coll)

    total = await query.count()
    pages = math.ceil(total / limit) if total > 0 else 1
    offset = (page - 1) * limit

    entries = await query.offset(offset).limit(limit).prefetch_related("card")
    result = [_serialize_entry(e, e.card) for e in entries]

    if total > 0:
        all_entries = await query.values("quantity", "card_id")
        total_quantity = sum(e["quantity"] for e in all_entries)
        unique_card_ids = {e["card_id"] for e in all_entries}
        unique_names_list = await Card.filter(scryfall_id__in=list(unique_card_ids)).values_list("name", flat=True)
        unique_names = len(set(unique_names_list))
    else:
        total_quantity = 0
        unique_names = 0

    return {
        "entries": result,
        "total": total,
        "total_quantity": total_quantity,
        "unique_names": unique_names,
        "page": page,
        "limit": limit,
        "pages": pages,
        "collection_id": coll.id,
        "collection_name": coll.name,
        "collection_type": coll.type,
    }


@router.post("/api/collection/import", response_model=dict)
async def import_collection_csv(
    file: UploadFile = File(...),
    collection_id: int = Query(default=None),
    current_user: User = Depends(get_current_user),
):
    if collection_id is not None:
        coll = await _require_collection(collection_id, current_user)
    else:
        coll = await _get_or_create_default_collection(current_user)

    if coll.type == "external":
        raise HTTPException(status_code=400, detail="External collections cannot be manually imported into")

    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    first_line = text.split("\n")[0]
    delimiter = "\t" if "\t" in first_line else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)

    added = 0
    updated = 0
    skipped = 0
    errors = []

    for row_num, row in enumerate(reader, start=2):
        scryfall_id = (row.get("Scryfall ID") or "").strip()
        quantity_str = (row.get("Quantity") or "1").strip()
        foil_str = (row.get("Foil") or "normal").strip().lower()

        if not scryfall_id:
            skipped += 1
            continue

        try:
            quantity = max(1, int(quantity_str))
        except (ValueError, TypeError):
            quantity = 1

        finish = foil_str if foil_str in ("foil", "etched", "glossy") else "nonfoil"

        card = await Card.filter(scryfall_id=scryfall_id).first()
        if not card:
            errors.append(f"Row {row_num}: Card not found (Scryfall ID: {scryfall_id})")
            skipped += 1
            continue

        existing = await UserCollection.filter(collection=coll, card=card, finish=finish).first()
        if existing:
            existing.quantity += quantity
            await existing.save()
            updated += 1
        else:
            await UserCollection.create(
                user=current_user,
                collection=coll,
                card=card,
                quantity=quantity,
                finish=finish,
            )
            added += 1

    return {
        "added": added,
        "updated": updated,
        "skipped": skipped,
        "errors": errors[:20],
        "total_processed": added + updated + skipped,
    }


@router.post("/api/collection", response_model=dict)
async def add_to_collection(
    entry_data: CollectionEntryCreate,
    current_user: User = Depends(get_current_user),
):
    if entry_data.collection_id is not None:
        coll = await _require_collection(entry_data.collection_id, current_user)
    else:
        coll = await _get_or_create_default_collection(current_user)

    if coll.type == "external":
        raise HTTPException(status_code=400, detail="External collections are read-only")

    card = await Card.filter(scryfall_id=entry_data.card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    existing = await UserCollection.filter(collection=coll, card=card, finish=entry_data.finish).first()
    if existing:
        existing.quantity += entry_data.quantity
        await existing.save()
        return {"id": existing.id, "message": "Updated existing entry", "quantity": existing.quantity}

    entry = await UserCollection.create(
        user=current_user,
        collection=coll,
        card=card,
        quantity=entry_data.quantity,
        finish=entry_data.finish,
    )
    return {"id": entry.id, "message": "Added to collection", "quantity": entry.quantity}


@router.put("/api/collection/{entry_id}", response_model=dict)
async def update_collection_entry(
    entry_id: int,
    update_data: CollectionEntryUpdate,
    current_user: User = Depends(get_current_user),
):
    entry = await UserCollection.filter(id=entry_id, user=current_user).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Collection entry not found")

    entry.quantity = update_data.quantity
    if update_data.finish is not None:
        entry.finish = update_data.finish
    if update_data.card_id is not None:
        card = await Card.filter(scryfall_id=update_data.card_id).first()
        if not card:
            raise HTTPException(status_code=404, detail="Card not found")
        entry.card = card
    await entry.save()

    return {"id": entry.id, "quantity": entry.quantity, "message": "Updated"}


@router.delete("/api/collection/{entry_id}", response_model=dict)
async def remove_from_collection(
    entry_id: int,
    current_user: User = Depends(get_current_user),
):
    entry = await UserCollection.filter(id=entry_id, user=current_user).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Collection entry not found")

    await entry.delete()
    return {"message": "Removed from collection"}


@router.get("/api/collection/{user_id}", response_model=dict)
async def get_user_collection(
    user_id: int,
    current_user: User = Depends(get_current_user),
):
    user = await User.filter(id=user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    entries = await UserCollection.filter(user=user).prefetch_related("card")

    result = [
        {
            "id": e.id,
            "card_id": e.card.scryfall_id,
            "card_name": e.card.name,
            "quantity": e.quantity,
            "finish": e.finish,
        }
        for e in entries
    ]

    return {"user_id": user_id, "username": user.username, "entries": result}
