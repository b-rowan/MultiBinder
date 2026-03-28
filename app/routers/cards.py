from fastapi import APIRouter, HTTPException, Query, Depends, Request
from fastapi.responses import HTMLResponse
from app.models.card import Card
from app.schemas.card import CardOut, CardSearchResult
from app.services.auth import get_current_user
from app.models.user import User
from tortoise import connections
from tortoise.expressions import Q
import math

router = APIRouter()
from app.templates import templates


@router.get("/cards", response_class=HTMLResponse)
async def cards_page(request: Request):
    return templates.TemplateResponse(request, "collection.html")


@router.get("/api/cards/search", response_model=CardSearchResult)
async def search_cards(
    q: str = Query(default="", description="Search query"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    color: str = Query(default="", description="Filter by color identity"),
    rarity: str = Query(default="", description="Filter by rarity"),
    card_type: str = Query(default="", description="Filter by type"),
    current_user: User = Depends(get_current_user),
):
    query = Card.all()

    if q:
        query = query.filter(name__icontains=q)

    if color:
        # JSONField LIKE workaround for SQLite (json_contains not implemented)
        conn = connections.get("default")
        rows = await conn.execute_query_dict(
            "SELECT scryfall_id FROM cards WHERE color_identity LIKE ?",
            [f'%"{color.upper()}"%'],
        )
        ids = [r["scryfall_id"] for r in rows]
        query = query.filter(scryfall_id__in=ids) if ids else query.none()

    if rarity:
        query = query.filter(rarity=rarity.lower())

    if card_type:
        query = query.filter(type_line__icontains=card_type)

    total = await query.count()
    pages = math.ceil(total / limit) if total > 0 else 1
    offset = (page - 1) * limit

    cards = await query.offset(offset).limit(limit).order_by("name")

    return CardSearchResult(
        cards=[CardOut.model_validate(c.__dict__) for c in cards],
        total=total,
        page=page,
        limit=limit,
        pages=pages,
    )


@router.get("/api/cards/{scryfall_id}", response_model=CardOut)
async def get_card(
    scryfall_id: str,
    current_user: User = Depends(get_current_user),
):
    card = await Card.filter(scryfall_id=scryfall_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    return CardOut.model_validate(card.__dict__)
