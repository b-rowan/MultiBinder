from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.schemas.card import CardOut
from app.schemas.user import UserOut


class DeckCreate(BaseModel):
    name: str
    description: Optional[str] = None
    format: str = "commander"
    is_shared: bool = False


class DeckUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    format: Optional[str] = None
    is_shared: Optional[bool] = None


class DeckCardOut(BaseModel):
    id: int
    card: CardOut
    quantity: int
    board: str

    class Config:
        from_attributes = True


class DeckOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    format: str
    is_shared: bool
    created_at: datetime
    updated_at: datetime
    owner_id: int
    owner_username: Optional[str] = None
    card_count: int = 0

    class Config:
        from_attributes = True


class DeckDetailOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    format: str
    is_shared: bool
    created_at: datetime
    updated_at: datetime
    owner: UserOut
    cards: List[DeckCardOut] = []
    collaborators: List[UserOut] = []

    class Config:
        from_attributes = True


class DeckCardCreate(BaseModel):
    card_id: str
    quantity: int = 1
    board: str = "main"


class DeckCardUpdate(BaseModel):
    quantity: Optional[int] = None
    board: Optional[str] = None


class DeckImport(BaseModel):
    list: str
    replace: bool = False


class CollaboratorAdd(BaseModel):
    username: str


class CardAvailability(BaseModel):
    card_id: str
    card_name: str
    needed: int
    owners: List[dict] = []  # [{user_id, username, quantity, foil: bool (any non-nonfoil finish)}]
    status: str  # "owned", "partial", "missing"
