from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        UPDATE "item" SET "tags" = (
            SELECT COALESCE(json_agg(DISTINCT value), '[]'::json)
            FROM (
                SELECT jsonb_array_elements_text(COALESCE("categories", '[]'::jsonb)) as value
                UNION
                SELECT jsonb_array_elements_text(COALESCE("tags", '[]'::jsonb)) as value
            ) AS combined_values
            WHERE value IS NOT NULL AND value != ''
        );
        ALTER TABLE "item" DROP COLUMN "categories";"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return ""
