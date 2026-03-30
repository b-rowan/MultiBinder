import re
import httpx
from app.models.card import Card, UserCollection

MOXFIELD_API_BASE = "https://api2.moxfield.com"

_BINDER_ID_RE = re.compile(r'moxfield\.com/binders/([A-Za-z0-9_-]+)')


def _parse_binder_id(url: str) -> str | None:
    m = _BINDER_ID_RE.search(url)
    return m.group(1) if m else None


def _normalize_finish(moxfield_finish: str) -> str:
    f = (moxfield_finish or "").lower()
    if "etched" in f:
        return "etched"
    if "foil" in f:
        return "foil"
    return "nonfoil"



def _extract_binder_cards(data: dict) -> list[dict]:
    """
    Extract cards from a Moxfield trade-binder response.

    The v1 trade-binder API returns cards as a dict keyed by card name,
    similar to deck boards.  Each entry looks like:
        {
          "quantity": 1,
          "foilQuantity": 0,
          "finish": "nonFoil",
          "card": { "name": ..., "scryfall_id": ..., "set": ..., "cn": ... }
        }
    We emit one entry per (card, finish) pair:
      - nonfoil quantity  → finish "nonfoil"
      - foilQuantity > 0  → finish "foil"
    """
    cards = []

    # The API may nest cards under a "cards" key or return them at the top level
    # under board-like keys.  Try the most common patterns.
    raw: dict = {}
    if "cards" in data and isinstance(data["cards"], dict):
        raw = data["cards"]
    elif "mainboard" in data and isinstance(data["mainboard"], dict):
        raw = data["mainboard"]
    else:
        # Fall back to treating any dict value whose entries contain a "card" key as the card list
        for v in data.values():
            if isinstance(v, dict):
                sample = next(iter(v.values()), {})
                if isinstance(sample, dict) and "card" in sample:
                    raw = v
                    break

    for card_name, entry in raw.items():
        if not isinstance(entry, dict):
            continue
        card_data = entry.get("card") or {}
        base = {
            "name": card_data.get("name") or card_name,
            "scryfall_id": card_data.get("scryfall_id") or card_data.get("scryfallId"),
            "set_code": card_data.get("set") or card_data.get("set_code"),
            "collector_number": card_data.get("cn") or card_data.get("collector_number"),
        }

        # Non-foil quantity
        qty = entry.get("quantity", 0)
        if qty > 0:
            cards.append({**base, "quantity": qty, "finish": "nonfoil"})

        # Foil quantity tracked separately in binder entries
        foil_qty = entry.get("foilQuantity", 0)
        if foil_qty > 0:
            cards.append({**base, "quantity": foil_qty, "finish": "foil"})

        # If neither field was present fall back to the finish field
        if qty == 0 and foil_qty == 0:
            cards.append({
                **base,
                "quantity": entry.get("quantity", 1),
                "finish": _normalize_finish(entry.get("finish", "")),
            })

    return cards


async def _fetch(client: httpx.AsyncClient, url: str) -> dict:
    resp = await client.get(url)
    resp.raise_for_status()
    return resp.json()


async def sync_moxfield_collection(collection) -> dict:
    """
    Sync a Collection from a Moxfield binder URL.
    Replaces all existing entries in the collection.
    Returns: {source_name, added, not_found}
    """
    if not collection.external_url:
        raise ValueError("Collection has no external URL set")

    public_id = _parse_binder_id(collection.external_url)
    if not public_id:
        raise ValueError(
            f"URL not recognised as a Moxfield binder: {collection.external_url}\n"
            "Expected format: https://www.moxfield.com/binders/<id>"
        )

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        data = await _fetch(client, f"{MOXFIELD_API_BASE}/v1/trade-binders/{public_id}/")
        print(data)

    source_name = data.get("name") or "Moxfield Binder"
    raw_cards = _extract_binder_cards(data)

    # Replace all existing entries
    await UserCollection.filter(collection=collection).delete()

    user = await collection.user
    added = 0
    not_found = []

    for entry in raw_cards:
        card = None

        if entry.get("scryfall_id"):
            card = await Card.filter(scryfall_id=entry["scryfall_id"]).first()

        if not card and entry.get("set_code") and entry.get("collector_number"):
            card = await Card.filter(
                set_code__iexact=entry["set_code"],
                collector_number=entry["collector_number"],
            ).first()

        if not card and entry.get("set_code"):
            card = await Card.filter(
                set_code__iexact=entry["set_code"],
                name=entry["name"],
            ).first()

        if not card:
            card = await Card.filter(name=entry["name"]).first()

        if not card:
            not_found.append(entry["name"])
            continue

        await UserCollection.create(
            user=user,
            collection=collection,
            card=card,
            quantity=entry["quantity"],
            finish=entry["finish"],
        )
        added += 1

    return {"source_name": source_name, "added": added, "not_found": not_found}
