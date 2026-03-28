from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "cards" ADD "finishes" JSON NOT NULL DEFAULT '[]';
        CREATE TABLE "user_collection_new" (
            "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            "quantity" INT NOT NULL DEFAULT 1,
            "finish" VARCHAR(20) NOT NULL DEFAULT 'nonfoil',
            "added_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "card_id" VARCHAR(36) NOT NULL REFERENCES "cards" ("scryfall_id") ON DELETE CASCADE,
            "user_id" INT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE,
            CONSTRAINT "uid_user_collec_user_id_0a47ec" UNIQUE ("user_id", "card_id", "finish")
        );
        INSERT INTO "user_collection_new" ("id", "quantity", "finish", "added_at", "card_id", "user_id")
            SELECT "id", "quantity", CASE WHEN "foil" = 1 THEN 'foil' ELSE 'nonfoil' END, "added_at", "card_id", "user_id"
            FROM "user_collection";
        DROP TABLE "user_collection";
        ALTER TABLE "user_collection_new" RENAME TO "user_collection";"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "cards" DROP COLUMN "finishes";
        CREATE TABLE "user_collection_old" (
            "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            "quantity" INT NOT NULL DEFAULT 1,
            "foil" INT NOT NULL DEFAULT 0,
            "added_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "card_id" VARCHAR(36) NOT NULL REFERENCES "cards" ("scryfall_id") ON DELETE CASCADE,
            "user_id" INT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE,
            CONSTRAINT "uid_user_collec_user_id_bc1d3c" UNIQUE ("user_id", "card_id", "foil")
        );
        INSERT INTO "user_collection_old" ("id", "quantity", "foil", "added_at", "card_id", "user_id")
            SELECT "id", "quantity", CASE WHEN "finish" = 'foil' THEN 1 ELSE 0 END, "added_at", "card_id", "user_id"
            FROM "user_collection";
        DROP TABLE "user_collection";
        ALTER TABLE "user_collection_old" RENAME TO "user_collection";"""


MODELS_STATE = (
    "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"
    "p+r+xsbx9p7uUvL4//AvLxQ74="
)
