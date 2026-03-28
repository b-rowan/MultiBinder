import httpx
import json
import asyncio
from typing import Callable, Optional
from app.models.card import Card

SCRYFALL_API = "https://api.scryfall.com"
USER_AGENT = "MultiBinder/1.0 (MTG Collection Tracker)"

# Global sync status
sync_status = {
    "running": False,
    "progress": 0,
    "total": 0,
    "processed": 0,
    "skipped": 0,
    "errors": 0,
    "last_sync": None,
    "message": "Never synced",
}


async def get_bulk_data_url() -> str:
    """Fetch the Scryfall bulk data endpoint and return the default_cards download URL."""
    async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}) as client:
        response = await client.get(f"{SCRYFALL_API}/bulk-data")
        response.raise_for_status()
        data = response.json()
        for item in data.get("data", []):
            if item.get("type") == "default_cards":
                return item["download_uri"]
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
                },
            )
            processed += 1
        except Exception as e:
            errors += 1
            continue

    return processed, skipped, errors


async def sync_cards(progress_callback: Optional[Callable] = None):
    """Download and sync all cards from Scryfall bulk data."""
    global sync_status

    sync_status["running"] = True
    sync_status["progress"] = 0
    sync_status["total"] = 0
    sync_status["processed"] = 0
    sync_status["skipped"] = 0
    sync_status["errors"] = 0
    sync_status["message"] = "Fetching bulk data URL..."

    try:
        download_url = await get_bulk_data_url()
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

                # Get content length if available
                content_length = response.headers.get("content-length")
                if content_length:
                    sync_status["message"] = f"Downloading {int(content_length) // 1024 // 1024}MB..."

                # Collect the full JSON content
                chunks = []
                async for chunk in response.aiter_bytes(chunk_size=65536):
                    chunks.append(chunk)

                full_content = b"".join(chunks)
                sync_status["message"] = "Parsing card data..."

                cards_data = json.loads(full_content)
                sync_status["total"] = len(cards_data)
                sync_status["message"] = f"Processing {len(cards_data)} cards..."

                for card_data in cards_data:
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
                        sync_status["progress"] = int(card_count / sync_status["total"] * 100)
                        sync_status["message"] = (
                            f"Processing... {card_count}/{sync_status['total']} cards"
                        )

                        if progress_callback:
                            await progress_callback(sync_status)

                        # Small yield to allow other requests to be handled
                        await asyncio.sleep(0)

                # Process remaining batch
                if current_batch:
                    processed, skipped, errors = await process_card_batch(current_batch)
                    total_processed += processed
                    total_skipped += skipped
                    total_errors += errors

        from datetime import datetime

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

    except Exception as e:
        sync_status["running"] = False
        sync_status["message"] = f"Sync failed: {str(e)}"
        sync_status["errors"] += 1
        raise
