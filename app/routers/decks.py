from fastapi import APIRouter, HTTPException, Depends, Request, Query
from fastapi.responses import HTMLResponse
from app.models.deck import Deck, DeckCard
from app.models.card import Card, UserCollection
from app.models.user import User
from app.schemas.deck import (
    DeckCreate, DeckUpdate, DeckOut, DeckDetailOut,
    DeckCardCreate, DeckCardUpdate, DeckImport, CollaboratorAdd, CardAvailability,
)
from app.services.auth import get_current_user
from typing import List
from tortoise.expressions import Q
import re

router = APIRouter()
from app.templates import templates


def _serialize_deck(deck: Deck, stats: dict = None, owner_username: str = None) -> dict:
    stats = stats or {}
    return {
        "id": deck.id,
        "name": deck.name,
        "description": deck.description,
        "format": deck.format,
        "is_shared": deck.is_shared,
        "created_at": deck.created_at.isoformat() if deck.created_at else None,
        "updated_at": deck.updated_at.isoformat() if deck.updated_at else None,
        "owner_id": deck.owner_id,
        "owner_username": owner_username,
        "card_count": stats.get("main", 0),
        "main_count": stats.get("main", 0),
        "side_count": stats.get("side", 0),
        "unique_count": stats.get("unique", 0),
    }


async def _deck_stats(deck_ids: list[int]) -> dict[int, dict]:
    """Return {deck_id: {main, side, unique}} for a list of deck IDs."""
    if not deck_ids:
        return {}
    rows = await DeckCard.filter(deck_id__in=deck_ids).values("deck_id", "board", "quantity", "card_id")
    stats: dict[int, dict] = {did: {"main": 0, "side": 0, "cards": set()} for did in deck_ids}
    for row in rows:
        did = row["deck_id"]
        if row["board"] in ("main", "commander"):
            stats[did]["main"] += row["quantity"]
        elif row["board"] == "side":
            stats[did]["side"] += row["quantity"]
        stats[did]["cards"].add(row["card_id"])
    return {did: {"main": v["main"], "side": v["side"], "unique": len(v["cards"])} for did, v in stats.items()}


@router.get("/decks", response_class=HTMLResponse)
async def decks_page(request: Request):
    return templates.TemplateResponse(request, "decks.html", )


@router.get("/decks/{deck_id}", response_class=HTMLResponse)
async def deck_detail_page(request: Request, deck_id: int):
    return templates.TemplateResponse(request, "deck_detail.html", {"deck_id": deck_id})


@router.get("/api/decks", response_model=dict)
async def list_decks(current_user: User = Depends(get_current_user)):
    owned = await Deck.filter(owner=current_user).prefetch_related("owner")
    shared_decks = await Deck.filter(collaborators=current_user).prefetch_related("owner")

    all_ids = [d.id for d in owned] + [d.id for d in shared_decks]
    stats = await _deck_stats(all_ids)

    owned_list = [_serialize_deck(d, stats.get(d.id), current_user.username) for d in owned]

    shared_list = []
    for deck in shared_decks:
        owner = await deck.owner
        shared_list.append(_serialize_deck(deck, stats.get(deck.id), owner.username))

    return {"owned": owned_list, "shared": shared_list}


@router.post("/api/decks", response_model=dict)
async def create_deck(
    deck_data: DeckCreate,
    current_user: User = Depends(get_current_user),
):
    deck = await Deck.create(
        name=deck_data.name,
        description=deck_data.description,
        format=deck_data.format,
        is_shared=deck_data.is_shared,
        owner=current_user,
    )
    return _serialize_deck(deck, 0, current_user.username)


@router.get("/api/decks/{deck_id}", response_model=dict)
async def get_deck(
    deck_id: int,
    current_user: User = Depends(get_current_user),
):
    deck = await Deck.filter(id=deck_id).prefetch_related("owner", "collaborators").first()
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")

    owner = await deck.owner
    collaborators = await deck.collaborators.all()

    # Check access
    collab_ids = [c.id for c in collaborators]
    if owner.id != current_user.id and current_user.id not in collab_ids:
        raise HTTPException(status_code=403, detail="Access denied")

    # Get cards
    deck_cards = await DeckCard.filter(deck=deck).prefetch_related("card")
    cards_list = []
    for dc in deck_cards:
        card = dc.card
        cards_list.append({
            "id": dc.id,
            "quantity": dc.quantity,
            "board": dc.board,
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
                "rarity": card.rarity,
                "image_uri_small": card.image_uri_small,
                "image_uri_normal": card.image_uri_normal,
                "power": card.power,
                "toughness": card.toughness,
                "loyalty": card.loyalty,
                "layout": card.layout,
                "legalities": card.legalities,
                "card_faces": card.card_faces,
            },
        })

    return {
        "id": deck.id,
        "name": deck.name,
        "description": deck.description,
        "format": deck.format,
        "is_shared": deck.is_shared,
        "created_at": deck.created_at.isoformat() if deck.created_at else None,
        "updated_at": deck.updated_at.isoformat() if deck.updated_at else None,
        "owner": {
            "id": owner.id,
            "username": owner.username,
            "email": owner.email,
            "is_admin": owner.is_admin,
            "created_at": owner.created_at.isoformat() if owner.created_at else None,
        },
        "collaborators": [
            {
                "id": c.id,
                "username": c.username,
                "email": c.email,
                "is_admin": c.is_admin,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in collaborators
        ],
        "cards": cards_list,
    }


@router.put("/api/decks/{deck_id}", response_model=dict)
async def update_deck(
    deck_id: int,
    update_data: DeckUpdate,
    current_user: User = Depends(get_current_user),
):
    deck = await Deck.filter(id=deck_id, owner=current_user).first()
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found or access denied")

    if update_data.name is not None:
        deck.name = update_data.name
    if update_data.description is not None:
        deck.description = update_data.description
    if update_data.format is not None:
        deck.format = update_data.format
    if update_data.is_shared is not None:
        deck.is_shared = update_data.is_shared

    await deck.save()
    return {"message": "Deck updated", "id": deck.id}


@router.delete("/api/decks/{deck_id}", response_model=dict)
async def delete_deck(
    deck_id: int,
    current_user: User = Depends(get_current_user),
):
    deck = await Deck.filter(id=deck_id, owner=current_user).first()
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found or access denied")

    await deck.delete()
    return {"message": "Deck deleted"}


@router.post("/api/decks/{deck_id}/cards", response_model=dict)
async def add_card_to_deck(
    deck_id: int,
    card_data: DeckCardCreate,
    current_user: User = Depends(get_current_user),
):
    deck = await Deck.filter(id=deck_id).prefetch_related("collaborators").first()
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")

    owner = await deck.owner
    collaborators = await deck.collaborators.all()
    collab_ids = [c.id for c in collaborators]

    if owner.id != current_user.id and current_user.id not in collab_ids:
        raise HTTPException(status_code=403, detail="Access denied")

    card = await Card.filter(scryfall_id=card_data.card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    existing = await DeckCard.filter(deck=deck, card=card, board=card_data.board).first()
    if existing:
        existing.quantity += card_data.quantity
        await existing.save()
        return {"id": existing.id, "message": "Updated quantity", "quantity": existing.quantity}

    dc = await DeckCard.create(
        deck=deck,
        card=card,
        quantity=card_data.quantity,
        board=card_data.board,
    )
    return {"id": dc.id, "message": "Card added to deck", "quantity": dc.quantity}


@router.put("/api/decks/{deck_id}/cards/{deck_card_id}", response_model=dict)
async def update_deck_card(
    deck_id: int,
    deck_card_id: int,
    update_data: DeckCardUpdate,
    current_user: User = Depends(get_current_user),
):
    deck = await Deck.filter(id=deck_id).first()
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")

    owner = await deck.owner
    collaborators = await deck.collaborators.all()
    collab_ids = [c.id for c in collaborators]

    if owner.id != current_user.id and current_user.id not in collab_ids:
        raise HTTPException(status_code=403, detail="Access denied")

    dc = await DeckCard.filter(id=deck_card_id, deck=deck).first()
    if not dc:
        raise HTTPException(status_code=404, detail="Deck card not found")

    if update_data.quantity is not None:
        dc.quantity = update_data.quantity
    if update_data.board is not None:
        dc.board = update_data.board

    await dc.save()
    return {"message": "Updated", "id": dc.id}


@router.delete("/api/decks/{deck_id}/cards/{deck_card_id}", response_model=dict)
async def remove_card_from_deck(
    deck_id: int,
    deck_card_id: int,
    current_user: User = Depends(get_current_user),
):
    deck = await Deck.filter(id=deck_id).first()
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")

    owner = await deck.owner
    collaborators = await deck.collaborators.all()
    collab_ids = [c.id for c in collaborators]

    if owner.id != current_user.id and current_user.id not in collab_ids:
        raise HTTPException(status_code=403, detail="Access denied")

    dc = await DeckCard.filter(id=deck_card_id, deck=deck).first()
    if not dc:
        raise HTTPException(status_code=404, detail="Deck card not found")

    await dc.delete()
    return {"message": "Card removed from deck"}


_LINE_RE = re.compile(r'^(\d+)\s+(.+)$')


def _parse_deck_list(text: str) -> list[dict]:
    entries = []
    current_board = "main"
    seen_main_card = False
    for line in text.splitlines():
        line = line.strip()
        if not line:
            # A blank line after at least one mainboard card → sideboard
            if current_board == "main" and seen_main_card:
                current_board = "side"
            continue
        if line.startswith("//"):
            section = line.lstrip("/").strip().lower()
            if "side" in section:
                current_board = "side"
            elif "commander" in section or "cmdr" in section:
                current_board = "commander"
            else:
                current_board = "main"
            continue
        m = _LINE_RE.match(line)
        if m:
            name = m.group(2).strip()
            # Normalise split-card names: "Wear/Tear" → "Wear // Tear"
            name = re.sub(r'\s*/\s*', ' // ', name)
            entries.append({
                "quantity": int(m.group(1)),
                "name": name,
                "board": current_board,
            })
            if current_board == "main":
                seen_main_card = True
    return entries


@router.post("/api/decks/{deck_id}/import", response_model=dict)
async def import_deck_list(
    deck_id: int,
    import_data: DeckImport,
    current_user: User = Depends(get_current_user),
):
    deck = await Deck.filter(id=deck_id).prefetch_related("collaborators").first()
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")

    owner = await deck.owner
    collaborators = await deck.collaborators.all()
    if owner.id != current_user.id and current_user.id not in [c.id for c in collaborators]:
        raise HTTPException(status_code=403, detail="Access denied")

    if import_data.replace:
        await DeckCard.filter(deck=deck).delete()

    entries = _parse_deck_list(import_data.list)
    added = 0
    updated = 0
    not_found = []

    for entry in entries:
        card = await Card.filter(name=entry["name"]).first()

        # Fallback: front face of a double-faced card ("Ral, Monsoon Mage" → "Ral, Monsoon Mage // ...")
        if not card:
            card = await Card.filter(name__startswith=entry["name"] + " // ").first()

        if not card:
            not_found.append(f"{entry['quantity']} {entry['name']}")
            continue

        existing = await DeckCard.filter(deck=deck, card=card, board=entry["board"]).first()
        if existing:
            existing.quantity += entry["quantity"]
            await existing.save()
            updated += 1
        else:
            await DeckCard.create(
                deck=deck,
                card=card,
                quantity=entry["quantity"],
                board=entry["board"],
            )
            added += 1

    return {
        "added": added,
        "updated": updated,
        "not_found": not_found,
        "total_parsed": len(entries),
    }


@router.get("/api/users/search", response_model=list)
async def search_users(
    q: str = Query("", min_length=0),
    current_user: User = Depends(get_current_user),
):
    if not q or len(q) < 1:
        return []
    users = await User.filter(username__icontains=q).exclude(id=current_user.id).limit(8).values("id", "username")
    return users


@router.post("/api/decks/{deck_id}/collaborators", response_model=dict)
async def add_collaborator(
    deck_id: int,
    collab_data: CollaboratorAdd,
    current_user: User = Depends(get_current_user),
):
    deck = await Deck.filter(id=deck_id, owner=current_user).first()
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found or access denied")

    user = await User.filter(username=collab_data.username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot add yourself as collaborator")

    await deck.collaborators.add(user)
    deck.is_shared = True
    await deck.save()

    return {"message": f"Added {user.username} as collaborator"}


@router.delete("/api/decks/{deck_id}/collaborators/{user_id}", response_model=dict)
async def remove_collaborator(
    deck_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user),
):
    deck = await Deck.filter(id=deck_id, owner=current_user).first()
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found or access denied")

    user = await User.filter(id=user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await deck.collaborators.remove(user)

    # If no more collaborators, mark as not shared
    collab_count = await deck.collaborators.all().count()
    if collab_count == 0:
        deck.is_shared = False
        await deck.save()

    return {"message": f"Removed collaborator"}


@router.get("/api/decks/{deck_id}/availability", response_model=dict)
async def get_deck_availability(
    deck_id: int,
    current_user: User = Depends(get_current_user),
):
    deck = await Deck.filter(id=deck_id).first()
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")

    owner = await deck.owner
    collaborators = await deck.collaborators.all()
    collab_ids = [c.id for c in collaborators]

    if owner.id != current_user.id and current_user.id not in collab_ids:
        raise HTTPException(status_code=403, detail="Access denied")

    # All participants (owner + collaborators)
    all_participants = [owner] + list(collaborators)
    other_participants = [p for p in all_participants if p.id != current_user.id]

    # Precompute current user's other deck IDs (owned or collaborated, excluding this deck)
    user_other_deck_ids = set(
        await Deck.filter(owner=current_user).exclude(id=deck_id).values_list("id", flat=True)
    )
    user_other_deck_ids.update(
        await Deck.filter(collaborators=current_user).exclude(id=deck_id).values_list("id", flat=True)
    )
    user_other_deck_ids = list(user_other_deck_ids)

    # Precompute other participants' other deck IDs (excluding this deck)
    collab_other_deck_ids = set()
    for p in other_participants:
        collab_other_deck_ids.update(
            await Deck.filter(owner=p).exclude(id=deck_id).values_list("id", flat=True)
        )
        collab_other_deck_ids.update(
            await Deck.filter(collaborators=p).exclude(id=deck_id).values_list("id", flat=True)
        )
    collab_other_deck_ids = list(collab_other_deck_ids)

    # Get all deck cards
    deck_cards = await DeckCard.filter(deck=deck).prefetch_related("card")

    availability = []
    for dc in deck_cards:
        card = dc.card
        needed = dc.quantity

        # Basic lands are always considered available
        if card.type_line and "Basic Land" in card.type_line:
            availability.append({
                "card_id": card.scryfall_id,
                "card_name": card.name,
                "deck_card_id": dc.id,
                "board": dc.board,
                "needed": needed,
                "owners": [],
                "status": "owned",
            })
            continue

        # Match any printing of the same card name
        same_name_ids = await Card.filter(name=card.name).values_list("scryfall_id", flat=True)
        same_name_ids = list(same_name_ids)

        owners_data = []
        for participant in all_participants:
            entries = await UserCollection.filter(
                user=participant, card_id__in=same_name_ids
            ).all()
            total_qty = sum(e.quantity for e in entries)
            if total_qty > 0:
                owners_data.append({
                    "user_id": participant.id,
                    "username": participant.username,
                    "quantity": total_qty,
                    "foil": any(e.finish != "nonfoil" for e in entries),
                })

        user_qty = sum(o["quantity"] for o in owners_data if o["user_id"] == current_user.id)
        collab_qty = sum(o["quantity"] for o in owners_data if o["user_id"] != current_user.id)

        # User's copies committed to their other decks
        if user_other_deck_ids:
            user_other_dcs = await DeckCard.filter(
                deck_id__in=user_other_deck_ids, card_id__in=same_name_ids
            ).all()
            user_in_use = sum(d.quantity for d in user_other_dcs)
        else:
            user_in_use = 0

        # Collaborators' copies committed to their other decks
        if collab_other_deck_ids:
            collab_other_dcs = await DeckCard.filter(
                deck_id__in=collab_other_deck_ids, card_id__in=same_name_ids
            ).all()
            collab_in_use = sum(d.quantity for d in collab_other_dcs)
        else:
            collab_in_use = 0

        user_free = max(0, user_qty - user_in_use)
        collab_free = max(0, collab_qty - collab_in_use)

        # Evaluate in priority order: user-first, then combined, then collab, then partial
        if user_free >= needed:
            status = "owned"              # user alone has enough free copies
        elif user_qty >= needed:
            status = "owned_in_use"       # user alone has enough but they're in other decks
        elif user_qty > 0 and user_free + collab_free >= needed:
            status = "mixed_you_enough"   # user + collab free copies cover it together
        elif user_qty > 0 and user_qty + collab_qty >= needed:
            status = "mixed_in_use"       # combined total covers it but some are in other decks
        elif collab_free >= needed:
            status = "collab_owned"       # collab alone has enough free copies
        elif collab_qty >= needed:
            status = "collab_in_use"      # collab alone has enough but they're in other decks
        elif user_qty > 0 and collab_qty > 0:
            status = "partial_mixed"      # both have some but combined not enough
        elif user_qty > 0:
            status = "partial"            # only user has some, not enough
        elif collab_qty > 0:
            status = "collab_partial"     # only collab has some, not enough
        else:
            status = "missing"

        availability.append({
            "card_id": card.scryfall_id,
            "card_name": card.name,
            "deck_card_id": dc.id,
            "board": dc.board,
            "needed": needed,
            "owners": owners_data,
            "status": status,
        })

    return {"availability": availability, "deck_id": deck_id}
