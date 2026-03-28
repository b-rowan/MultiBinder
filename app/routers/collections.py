from fastapi import APIRouter, HTTPException, Depends, Request, Query, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.models.card import Card, UserCollection
from app.models.user import User
from app.schemas.card import CollectionEntryCreate, CollectionEntryUpdate, CollectionEntryOut, CardOut
from app.services.auth import get_current_user
from typing import List
import math
import csv
import io

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/collection", response_class=HTMLResponse)
async def collection_page(request: Request):
    return templates.TemplateResponse(request, "collection.html")


@router.get("/api/collection", response_model=dict)
async def get_my_collection(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=40, ge=1, le=100),
    q: str = Query(default=""),
    current_user: User = Depends(get_current_user),
):
    query = UserCollection.filter(user=current_user).prefetch_related("card")

    if q:
        # We need to filter via card name - use a subquery approach
        matching_cards = await Card.filter(name__icontains=q).values_list("scryfall_id", flat=True)
        query = UserCollection.filter(user=current_user, card_id__in=list(matching_cards))

    total = await query.count()
    pages = math.ceil(total / limit) if total > 0 else 1
    offset = (page - 1) * limit

    entries = await query.offset(offset).limit(limit).prefetch_related("card")

    result = []
    for entry in entries:
        card = entry.card
        result.append({
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
            "foil": entry.foil,
            "added_at": entry.added_at.isoformat() if entry.added_at else None,
        })

    return {
        "entries": result,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": pages,
    }


@router.get("/api/collection/{user_id}", response_model=dict)
async def get_user_collection(
    user_id: int,
    current_user: User = Depends(get_current_user),
):
    user = await User.filter(id=user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    entries = await UserCollection.filter(user=user).prefetch_related("card")

    result = []
    for entry in entries:
        card = entry.card
        result.append({
            "id": entry.id,
            "card_id": card.scryfall_id,
            "card_name": card.name,
            "quantity": entry.quantity,
            "foil": entry.foil,
        })

    return {"user_id": user_id, "username": user.username, "entries": result}


@router.post("/api/collection", response_model=dict)
async def add_to_collection(
    entry_data: CollectionEntryCreate,
    current_user: User = Depends(get_current_user),
):
    card = await Card.filter(scryfall_id=entry_data.card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    # Check if entry already exists
    existing = await UserCollection.filter(
        user=current_user, card=card, foil=entry_data.foil
    ).first()

    if existing:
        existing.quantity += entry_data.quantity
        await existing.save()
        return {"id": existing.id, "message": "Updated existing entry", "quantity": existing.quantity}

    entry = await UserCollection.create(
        user=current_user,
        card=card,
        quantity=entry_data.quantity,
        foil=entry_data.foil,
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
    await entry.save()

    return {"id": entry.id, "quantity": entry.quantity, "message": "Updated"}


@router.post("/api/collection/import", response_model=dict)
async def import_collection_csv(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    # Detect delimiter: tab if a tab exists in the header line, else comma
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

        foil = foil_str == "foil"

        card = await Card.filter(scryfall_id=scryfall_id).first()
        if not card:
            errors.append(f"Row {row_num}: Card not found (Scryfall ID: {scryfall_id})")
            skipped += 1
            continue

        existing = await UserCollection.filter(
            user=current_user, card=card, foil=foil
        ).first()

        if existing:
            existing.quantity += quantity
            await existing.save()
            updated += 1
        else:
            await UserCollection.create(
                user=current_user,
                card=card,
                quantity=quantity,
                foil=foil,
            )
            added += 1

    return {
        "added": added,
        "updated": updated,
        "skipped": skipped,
        "errors": errors[:20],
        "total_processed": added + updated + skipped,
    }


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
