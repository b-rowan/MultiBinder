from tortoise import fields
from tortoise.models import Model


class User(Model):
    id = fields.IntField(pk=True)
    username = fields.CharField(max_length=50, unique=True)
    email = fields.CharField(max_length=255, unique=True)
    hashed_password = fields.CharField(max_length=255)
    is_admin = fields.BooleanField(default=False)
    created_at = fields.DatetimeField(auto_now_add=True)

    # Reverse relations
    collection: fields.ReverseRelation["UserCollection"]
    collections: fields.ReverseRelation["Collection"]
    owned_decks: fields.ReverseRelation["Deck"]

    class Meta:
        table = "users"
