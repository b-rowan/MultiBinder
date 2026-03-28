from tortoise import Tortoise
from aerich import Command
from app.config import settings

AERICH_TORTOISE_ORM = {
    "connections": {"default": "sqlite://./app/multibinder.sqlite3"},
    "apps": {
        "models": {
            "models": ["app.models.user", "app.models.card", "app.models.deck", "aerich.models"],
            "default_connection": "default",
        }
    },
}

TORTOISE_ORM = {
    "connections": {"default": settings.database_url},
    "apps": {
        "models": {
            "models": ["app.models.user", "app.models.card", "app.models.deck", "aerich.models"],
            "default_connection": "default",
        }
    },
}


async def init_db():
    await Tortoise.init(config=TORTOISE_ORM)
    command = Command(tortoise_config=TORTOISE_ORM, app="models", location="./migrations")
    await command.init()
    await command.upgrade(run_in_transaction=True)


async def close_db():
    await Tortoise.close_connections()
