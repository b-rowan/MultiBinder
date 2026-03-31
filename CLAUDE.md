# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the development server
python -m app

# Docker (production-style)
docker compose up

# Database migrations (Aerich — auto-run on startup, manual if needed)
aerich upgrade
aerich migrate --name "description_of_change"

# Install dependencies
poetry install
```

No test suite exists in this project.

## Architecture

**Stack**: FastAPI + Tortoise-ORM (async) + SQLite + Jinja2 templates + vanilla JS + Tailwind CSS (CDN/JIT)

**Entry point**: `app/__init__.py` creates the FastAPI app, mounts `/static`, registers 5 routers (auth, cards, collections, decks, admin), and runs DB init/migration on startup via lifespan context.

**Routing pattern**: Each router in `app/routers/` serves both HTML pages (returning `TemplateResponse`) and JSON API endpoints consumed by client-side JS. Pages are rendered server-side; interactivity is handled by `app/static/js/*.js` files that call the JSON endpoints.

**Database**: Tortoise-ORM with Aerich migrations. Config in `app/database.py` and `pyproject.toml` `[tool.aerich]` section. Migrations auto-apply on startup. Default: SQLite at `./multibinder.sqlite3`; override via `DATABASE_URL` env var for PostgreSQL.

**Authentication**: JWT (via python-jose) + bcrypt (SHA-256 prehash + bcrypt). `get_current_user()` and `get_current_admin_user()` in `app/services/auth.py` are FastAPI dependencies injected into protected routes.

**Key models** (`app/models/`):
- `User` — owns collections and decks, can be a deck collaborator
- `Card` — Scryfall card data, keyed on `scryfall_id`
- `UserCollection` — join table: user × card × finish (nonfoil/foil/etched) with quantity
- `Collection` — grouping of UserCollection entries
- `Deck` + `DeckCard` — decks with main/side/commander boards, many-to-many collaborators

**External integrations** (`app/services/`):
- `scryfall.py` — bulk card sync from Scryfall API, uses `ijson` for streaming JSON
- `moxfield.py` — deck import from Moxfield
- `manabox.py` — collection sync from Manabox

**Deck availability logic** (`app/routers/decks.py`, `get_deck_availability`): 10-tier priority system distinguishing user-owned-free, user-owned-in-use, collaborator-owned, and partial/missing states. Status names map to border colors in `app/static/js/decks.js` (`BORDER_COLORS`).

**Collection display**: `app/static/js/collection.js` supports grid (server-side pagination, 24/page) and list (client-side grouping by card name, 12 unique names/page) modes. List mode fetches all entries (limit=500) and groups client-side.

## Configuration

Settings loaded via pydantic-settings from `.env` (optional):
- `SECRET_KEY` — required in production
- `DATABASE_URL` — defaults to `sqlite://./multibinder.sqlite3`
- `ACCESS_TOKEN_EXPIRE_MINUTES` — defaults to 10080 (7 days)

## Deployment

The `install.sh` script automates Proxmox LXC container setup. `docker-compose.yml` includes an optional Pangolin/Newt reverse proxy profile (`--profile pangolin`).
