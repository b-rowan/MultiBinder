from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "users" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "username" VARCHAR(50) NOT NULL UNIQUE,
    "email" VARCHAR(255) NOT NULL UNIQUE,
    "hashed_password" VARCHAR(255) NOT NULL,
    "is_admin" INT NOT NULL DEFAULT 0,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS "cards" (
    "scryfall_id" VARCHAR(36) NOT NULL PRIMARY KEY,
    "name" VARCHAR(255) NOT NULL,
    "mana_cost" VARCHAR(100),
    "cmc" REAL NOT NULL DEFAULT 0,
    "type_line" VARCHAR(255),
    "oracle_text" TEXT,
    "colors" JSON NOT NULL,
    "color_identity" JSON NOT NULL,
    "set_code" VARCHAR(10),
    "set_name" VARCHAR(255),
    "collector_number" VARCHAR(20),
    "rarity" VARCHAR(20),
    "image_uri_small" VARCHAR(500),
    "image_uri_normal" VARCHAR(500),
    "image_uri_large" VARCHAR(500),
    "power" VARCHAR(10),
    "toughness" VARCHAR(10),
    "loyalty" VARCHAR(10),
    "layout" VARCHAR(50),
    "card_faces" JSON,
    "legalities" JSON NOT NULL
);
CREATE INDEX IF NOT EXISTS "idx_cards_name_61fb72" ON "cards" ("name");
CREATE TABLE IF NOT EXISTS "user_collection" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "quantity" INT NOT NULL DEFAULT 1,
    "foil" INT NOT NULL DEFAULT 0,
    "added_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "card_id" VARCHAR(36) NOT NULL REFERENCES "cards" ("scryfall_id") ON DELETE CASCADE,
    "user_id" INT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_user_collec_user_id_bc1d3c" UNIQUE ("user_id", "card_id", "foil")
);
CREATE TABLE IF NOT EXISTS "decks" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "name" VARCHAR(255) NOT NULL,
    "description" TEXT,
    "is_shared" INT NOT NULL DEFAULT 0,
    "format" VARCHAR(50) NOT NULL DEFAULT 'commander',
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "owner_id" INT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "deck_cards" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "quantity" INT NOT NULL DEFAULT 1,
    "board" VARCHAR(20) NOT NULL DEFAULT 'main',
    "card_id" VARCHAR(36) NOT NULL REFERENCES "cards" ("scryfall_id") ON DELETE CASCADE,
    "deck_id" INT NOT NULL REFERENCES "decks" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_deck_cards_deck_id_93a9e7" UNIQUE ("deck_id", "card_id", "board")
);
CREATE TABLE IF NOT EXISTS "aerich" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "version" VARCHAR(255) NOT NULL,
    "app" VARCHAR(100) NOT NULL,
    "content" JSON NOT NULL
);
CREATE TABLE IF NOT EXISTS "deck_collaborators" (
    "decks_id" INT NOT NULL REFERENCES "decks" ("id") ON DELETE CASCADE,
    "user_id" INT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS "uidx_deck_collab_decks_i_fc3c1a" ON "deck_collaborators" ("decks_id", "user_id");"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """


MODELS_STATE = (
    "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"
)
