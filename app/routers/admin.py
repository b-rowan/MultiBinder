import asyncio
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse
from app.models.user import User
from app.models.card import Card, UserCollection
from app.models.deck import Deck
from app.services.auth import get_current_admin_user, get_current_user
from app.services.scryfall import sync_cards, sync_status

from app import templates

router = APIRouter()


@router.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    return templates.TemplateResponse(request, "admin.html")


@router.post("/api/admin/sync-cards", response_model=dict)
async def trigger_sync(current_user: User = Depends(get_current_admin_user)):
    if sync_status["running"]:
        return {"message": "Sync already in progress", "status": sync_status}

    # Run sync in background
    asyncio.create_task(sync_cards())

    return {"message": "Card sync started", "status": sync_status}


@router.get("/api/admin/sync-status", response_model=dict)
async def get_sync_status(current_user: User = Depends(get_current_user)):
    return sync_status


@router.get("/api/admin/stats", response_model=dict)
async def get_stats(current_user: User = Depends(get_current_admin_user)):
    card_count = await Card.all().count()
    user_count = await User.all().count()
    collection_count = await UserCollection.all().count()
    deck_count = await Deck.all().count()

    return {
        "card_count": card_count,
        "user_count": user_count,
        "collection_entries": collection_count,
        "deck_count": deck_count,
        "sync_status": sync_status,
    }


@router.get("/api/admin/users", response_model=dict)
async def list_users(current_user: User = Depends(get_current_admin_user)):
    users = await User.all()
    return {
        "users": [
            {
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "is_admin": u.is_admin,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u in users
        ]
    }


@router.put("/api/admin/users/{user_id}/toggle-admin", response_model=dict)
async def toggle_admin(
    user_id: int,
    current_user: User = Depends(get_current_admin_user),
):
    user = await User.filter(id=user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot modify your own admin status")

    user.is_admin = not user.is_admin
    await user.save()

    return {"message": f"Admin status set to {user.is_admin}", "is_admin": user.is_admin}
