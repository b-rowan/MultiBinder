from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "collections" (
            "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            "name" VARCHAR(255) NOT NULL,
            "description" TEXT NOT NULL DEFAULT '',
            "type" VARCHAR(20) NOT NULL DEFAULT 'personal',
            "external_source" VARCHAR(50),
            "external_url" VARCHAR(500),
            "last_synced" TIMESTAMP,
            "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "user_id" INT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS "idx_collections_user_id" ON "collections" ("user_id");

        INSERT INTO "collections" ("name", "type", "created_at", "user_id")
            SELECT DISTINCT 'My Collection', 'personal', CURRENT_TIMESTAMP, "user_id"
            FROM "user_collection";

        CREATE TABLE "user_collection_new" (
            "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            "quantity" INT NOT NULL DEFAULT 1,
            "finish" VARCHAR(20) NOT NULL DEFAULT 'nonfoil',
            "added_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "card_id" VARCHAR(36) NOT NULL REFERENCES "cards" ("scryfall_id") ON DELETE CASCADE,
            "user_id" INT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE,
            "collection_id" INT NOT NULL REFERENCES "collections" ("id") ON DELETE CASCADE,
            CONSTRAINT "uid_user_collec_coll_card_finish" UNIQUE ("collection_id", "card_id", "finish")
        );
        CREATE INDEX IF NOT EXISTS "idx_user_collection_collection_id" ON "user_collection_new" ("collection_id");

        INSERT INTO "user_collection_new" ("id", "quantity", "finish", "added_at", "card_id", "user_id", "collection_id")
            SELECT uc."id", uc."quantity", uc."finish", uc."added_at", uc."card_id", uc."user_id", c."id"
            FROM "user_collection" uc
            JOIN "collections" c ON c."user_id" = uc."user_id";

        DROP TABLE "user_collection";
        ALTER TABLE "user_collection_new" RENAME TO "user_collection";"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE "user_collection_old" (
            "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            "quantity" INT NOT NULL DEFAULT 1,
            "finish" VARCHAR(20) NOT NULL DEFAULT 'nonfoil',
            "added_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "card_id" VARCHAR(36) NOT NULL REFERENCES "cards" ("scryfall_id") ON DELETE CASCADE,
            "user_id" INT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE,
            CONSTRAINT "uid_user_collec_user_id_0a47ec" UNIQUE ("user_id", "card_id", "finish")
        );
        INSERT INTO "user_collection_old" ("id", "quantity", "finish", "added_at", "card_id", "user_id")
            SELECT uc."id", uc."quantity", uc."finish", uc."added_at", uc."card_id", uc."user_id"
            FROM "user_collection" uc;
        DROP TABLE "user_collection";
        ALTER TABLE "user_collection_old" RENAME TO "user_collection";
        DROP TABLE "collections";"""


MODELS_STATE = (
    "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"
)
