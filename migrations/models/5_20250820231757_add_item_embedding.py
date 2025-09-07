from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "itemembedding" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "embedding" JSONB NOT NULL,
    "model_version" VARCHAR(50) NOT NULL,
    "dimension" INT NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "item_id" INT NOT NULL UNIQUE REFERENCES "item" ("id") ON DELETE CASCADE
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "itemembedding";"""
