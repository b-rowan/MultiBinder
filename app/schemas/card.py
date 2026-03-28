from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime


class CardOut(BaseModel):
    scryfall_id: str
    name: str
    mana_cost: Optional[str] = None
    cmc: float = 0
    type_line: Optional[str] = None
    oracle_text: Optional[str] = None
    colors: List[str] = []
    color_identity: List[str] = []
    set_code: Optional[str] = None
    set_name: Optional[str] = None
    collector_number: Optional[str] = None
    rarity: Optional[str] = None
    image_uri_small: Optional[str] = None
    image_uri_normal: Optional[str] = None
    image_uri_large: Optional[str] = None
    power: Optional[str] = None
    toughness: Optional[str] = None
    loyalty: Optional[str] = None
    layout: Optional[str] = None
    card_faces: Optional[Any] = None
    legalities: dict = {}

    class Config:
        from_attributes = True


class CollectionEntryCreate(BaseModel):
    card_id: str
    quantity: int = 1
    foil: bool = False


class CollectionEntryUpdate(BaseModel):
    quantity: int


class CollectionEntryOut(BaseModel):
    id: int
    card: CardOut
    quantity: int
    foil: bool
    added_at: datetime

    class Config:
        from_attributes = True


class CardSearchResult(BaseModel):
    cards: List[CardOut]
    total: int
    page: int
    limit: int
    pages: int
