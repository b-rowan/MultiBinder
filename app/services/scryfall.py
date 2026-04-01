import httpx
import ijson
import asyncio
import json
import os
from typing import Callable, Optional
from app.models.card import Card

SCRYFALL_API = "https://api.scryfall.com"
USER_AGENT = "MultiBinder/1.0 (MTG Collection Tracker)"
_SYNC_STATE_FILE = "scryfall_sync_state.json"


def _load_persisted_sync_state() -> dict:
    try:
        with open(_SYNC_STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_persisted_sync_state(state: dict):
    try:
        with open(_SYNC_STATE_FILE, "w") as f:
            json.dump(state, f)
    except Exception:
        pass


_persisted = _load_persisted_sync_state()

# Global sync status
sync_status = {
    "running": False,
    "progress": 0,
    "total": 0,
    "processed": _persisted.get("processed", 0),
    "skipped": _persisted.get("skipped", 0),
    "errors": 0,
    "last_sync": _persisted.get("last_sync", None),
    "message": f"Last sync: {_persisted['last_sync']}" if _persisted.get("last_sync") else "Never synced",
}


async def get_bulk_data_info() -> dict:
    """Fetch the Scryfall bulk data metadata and return the default_cards entry."""
    async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, timeout=httpx.Timeout(30.0)) as client:
        response = await client.get(f"{SCRYFALL_API}/bulk-data")
        response.raise_for_status()
        data = response.json()
        for item in data.get("data", []):
            if item.get("type") == "default_cards":
                return item
        raise ValueError("Could not find default_cards bulk data URL")


def extract_image_uris(card_data: dict) -> dict:
    """Extract image URIs, handling double-faced cards."""
    images = {"small": None, "normal": None, "large": None}

    if "image_uris" in card_data:
        uris = card_data["image_uris"]
        images["small"] = uris.get("small")
        images["normal"] = uris.get("normal")
        images["large"] = uris.get("large")
    elif "card_faces" in card_data and card_data["card_faces"]:
        # Use front face for double-faced cards
        front = card_data["card_faces"][0]
        if "image_uris" in front:
            uris = front["image_uris"]
            images["small"] = uris.get("small")
            images["normal"] = uris.get("normal")
            images["large"] = uris.get("large")

    return images


async def process_card_batch(batch: list) -> tuple[int, int, int]:
    """Process a batch of cards, upserting into the database."""
    processed = 0
    skipped = 0
    errors = 0

    for card_data in batch:
        try:
            images = extract_image_uris(card_data)

            # Skip cards without images
            if not images["small"] and not images["normal"]:
                skipped += 1
                continue

            # Prepare card_faces data (strip image_uris to save space)
            card_faces = None
            if card_data.get("card_faces"):
                card_faces = []
                for face in card_data["card_faces"]:
                    face_data = {
                        "name": face.get("name"),
                        "mana_cost": face.get("mana_cost"),
                        "type_line": face.get("type_line"),
                        "oracle_text": face.get("oracle_text"),
                        "power": face.get("power"),
                        "toughness": face.get("toughness"),
                        "loyalty": face.get("loyalty"),
                    }
                    if "image_uris" in face:
                        face_data["image_uris"] = face["image_uris"]
                    card_faces.append(face_data)

            card_obj, created = await Card.update_or_create(
                scryfall_id=card_data["id"],
                defaults={
                    "name": card_data.get("name", ""),
                    "mana_cost": card_data.get("mana_cost"),
                    "cmc": card_data.get("cmc", 0),
                    "type_line": card_data.get("type_line"),
                    "oracle_text": card_data.get("oracle_text"),
                    "colors": card_data.get("colors", []),
                    "color_identity": card_data.get("color_identity", []),
                    "set_code": card_data.get("set"),
                    "set_name": card_data.get("set_name"),
                    "collector_number": card_data.get("collector_number"),
                    "rarity": card_data.get("rarity"),
                    "image_uri_small": images["small"],
                    "image_uri_normal": images["normal"],
                    "image_uri_large": images["large"],
                    "power": card_data.get("power"),
                    "toughness": card_data.get("toughness"),
                    "loyalty": card_data.get("loyalty"),
                    "layout": card_data.get("layout"),
                    "card_faces": card_faces,
                    "legalities": card_data.get("legalities", {}),
                    "finishes": card_data.get("finishes", []),
                },
            )
            processed += 1
        except Exception as e:
            errors += 1
            continue

    return processed, skipped, errors


class _AsyncBytesReader:
    """Wraps an async bytes generator into a file-like object ijson can read."""
    def __init__(self, aiter):
        self._aiter = aiter
        self._buf = b""

    async def read(self, n=-1):
        if n == 0:
            return b""
        while len(self._buf) < n or n == -1:
            try:
                self._buf += await self._aiter.__anext__()
            except StopAsyncIteration:
                break
        if n == -1:
            data, self._buf = self._buf, b""
        else:
            data, self._buf = self._buf[:n], self._buf[n:]
        return data


async def sync_cards(progress_callback: Optional[Callable] = None, force: bool = False):
    """Download and sync all cards from Scryfall bulk data."""
    from datetime import datetime, timezone
    global sync_status

    sync_status["running"] = True
    sync_status["progress"] = 0
    sync_status["total"] = 0
    sync_status["processed"] = 0
    sync_status["skipped"] = 0
    sync_status["errors"] = 0
    sync_status["message"] = "Checking for updates..."

    try:
        bulk_info = await get_bulk_data_info()
        download_url = bulk_info["download_uri"]
        bulk_updated_at = bulk_info.get("updated_at", "")

        # Skip if bulk file hasn't changed since last sync
        last_bulk_updated = _persisted.get("bulk_updated_at")
        if not force and last_bulk_updated and bulk_updated_at and last_bulk_updated >= bulk_updated_at:
            sync_status["running"] = False
            sync_status["progress"] = 100
            sync_status["message"] = f"Already up to date (bulk data unchanged since {bulk_updated_at[:10]})."
            return
        sync_status["message"] = "Downloading card data..."

        batch_size = 500
        current_batch = []
        total_processed = 0
        total_skipped = 0
        total_errors = 0
        card_count = 0

        async with httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT},
            timeout=httpx.Timeout(300.0),
            follow_redirects=True,
        ) as client:
            async with client.stream("GET", download_url) as response:
                response.raise_for_status()

                content_length = response.headers.get("content-length")
                if content_length:
                    sync_status["message"] = f"Downloading {int(content_length) // 1024 // 1024}MB..."

                async for card_data in ijson.items_async(_AsyncBytesReader(response.aiter_bytes()), "item"):
                    current_batch.append(card_data)
                    card_count += 1

                    if len(current_batch) >= batch_size:
                        processed, skipped, errors = await process_card_batch(current_batch)
                        total_processed += processed
                        total_skipped += skipped
                        total_errors += errors
                        current_batch = []

                        sync_status["processed"] = total_processed
                        sync_status["skipped"] = total_skipped
                        sync_status["errors"] = total_errors
                        if content_length:
                            sync_status["progress"] = int(
                                response.num_bytes_downloaded / int(content_length) * 100
                            )
                        sync_status["message"] = f"Processing... {card_count} cards"

                        if progress_callback:
                            await progress_callback(sync_status)

                        await asyncio.sleep(0)

                # Process remaining batch
                if current_batch:
                    processed, skipped, errors = await process_card_batch(current_batch)
                    total_processed += processed
                    total_skipped += skipped
                    total_errors += errors

        sync_status["running"] = False
        sync_status["progress"] = 100
        sync_status["processed"] = total_processed
        sync_status["skipped"] = total_skipped
        sync_status["errors"] = total_errors
        sync_status["last_sync"] = datetime.utcnow().isoformat()
        sync_status["message"] = (
            f"Sync complete! {total_processed} cards synced, "
            f"{total_skipped} skipped, {total_errors} errors."
        )
        _persisted["last_sync"] = sync_status["last_sync"]
        _persisted["processed"] = total_processed
        _persisted["skipped"] = total_skipped
        _persisted["bulk_updated_at"] = bulk_updated_at
        _save_persisted_sync_state(_persisted)

    except Exception as e:
        sync_status["running"] = False
        sync_status["message"] = f"Sync failed: {str(e)}"
        sync_status["errors"] += 1
        raise
