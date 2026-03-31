import html as html_module
import httpx
import json
import re
from html.parser import HTMLParser
from app.models.card import Card, UserCollection

MANABOX_BASE = "https://manabox.app"

_DECK_ID_RE = re.compile(r'manabox\.app/decks/([A-Za-z0-9_-]+)')

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _parse_deck_id(url: str) -> str | None:
    m = _DECK_ID_RE.search(url)
    return m.group(1) if m else None


class _AstroPropsExtractor(HTMLParser):
    """Extract the props attribute from the first <astro-island> element."""

    def __init__(self):
        super().__init__()
        self.props_json: str | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "astro-island" and self.props_json is None:
            attrs_dict = dict(attrs)
            if attrs_dict.get("component-export") != "Main":
                return
            raw = attrs_dict.get("props", "")
            if raw:
                self.props_json = html_module.unescape(raw)


def _val(node):
    """
    ManaBox encodes every value as a [type, value] pair, e.g.
      [0, "Temple Garden"]   → "Temple Garden"
      [1, [...]]             → [...]   (list)
    This helper unwraps that envelope.
    """
    if isinstance(node, list) and len(node) >= 2:
        return node[1]
    return node


def _normalize_finish(variant: str) -> str:
    v = (variant or "").lower()
    if "etched" in v:
        return "etched"
    if "foil" in v:
        return "foil"
    return "nonfoil"


def _extract_cards(props: dict) -> list[dict]:
    """
    Walk the decoded props dict and return a flat list of card entries.
    Each entry has: name, quantity, finish, set_code, collector_number.
    Multiple entries for the same (name, finish, set, collector) are summed.
    """
    deck = _val(props.get("deck", []))
    if not isinstance(deck, dict):
        return []

    cards_raw = _val(deck.get("cards", []))
    if not isinstance(cards_raw, list):
        return []

    accumulated: dict[tuple, dict] = {}

    for item in cards_raw:
        card_data = _val(item)
        if not isinstance(card_data, dict):
            continue

        name = _val(card_data.get("name", [])) or ""
        quantity = _val(card_data.get("quantity", [])) or 1
        variant = _val(card_data.get("variant", [])) or "Normal"
        set_code = (_val(card_data.get("setId", [])) or "").lower() or None
        collector_number = _val(card_data.get("collectorNumber", []))
        collector_number = str(collector_number) if collector_number is not None else None

        if not name:
            continue

        finish = _normalize_finish(variant)
        key = (name, finish, set_code, collector_number)

        if key in accumulated:
            accumulated[key]["quantity"] += quantity
        else:
            accumulated[key] = {
                "name": name,
                "quantity": quantity,
                "finish": finish,
                "set_code": set_code,
                "collector_number": collector_number,
            }

    return list(accumulated.values())


async def sync_manabox_collection(collection) -> dict:
    """
    Sync a Collection from a ManaBox deck URL.
    Parses card data from the embedded <astro-island> props JSON.
    Replaces all existing entries in the collection.
    Returns: {source_name, added, not_found}
    """
    if not collection.external_url:
        raise ValueError("Collection has no external URL set")

    deck_id = _parse_deck_id(collection.external_url)
    if not deck_id:
        raise ValueError(
            f"URL not recognised as a ManaBox deck: {collection.external_url}\n"
            "Expected format: https://manabox.app/decks/<id>"
        )

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await client.get(
            f"{MANABOX_BASE}/decks/{deck_id}",
            headers=_HEADERS,
        )
        resp.raise_for_status()
        page_html = resp.text

    extractor = _AstroPropsExtractor()
    extractor.feed(page_html)

    if not extractor.props_json:
        raise ValueError(
            "Could not find the <astro-island> props on the ManaBox page. "
            "Make sure the deck is public and the URL is correct."
        )

    try:
        props = json.loads(extractor.props_json)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse ManaBox props JSON: {e}")


    raw_cards = _extract_cards(props)

    if not raw_cards:
        raise ValueError(
            "No cards found in the ManaBox deck data. "
            "Make sure the deck is public and contains cards."
        )

    try:
        deck_node = _val(props.get("deck", []))
        deck_name = _val(deck_node.get("name", [])) if isinstance(deck_node, dict) else None
        deck_name = deck_name or f"ManaBox deck {deck_id}"
    except Exception:
        deck_name = f"ManaBox deck {deck_id}"

    # Replace all existing entries
    await UserCollection.filter(collection=collection).delete()

    user = await collection.user
    added = 0
    not_found = []

    for entry in raw_cards:
        card = None

        # Best match: set code + collector number
        if entry["set_code"] and entry["collector_number"]:
            card = await Card.filter(
                set_code__iexact=entry["set_code"],
                collector_number=entry["collector_number"],
            ).first()

        # Fallback: name only
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

    return {"source_name": deck_name, "added": added, "not_found": not_found}
