from tortoise import fields
from tortoise.models import Model


class Deck(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=255)
    description = fields.TextField(null=True)
    owner = fields.ForeignKeyField("models.User", related_name="owned_decks")
    is_shared = fields.BooleanField(default=False)
    format = fields.CharField(max_length=50, default="commander")
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)
    collaborators = fields.ManyToManyField(
        "models.User", related_name="shared_decks", through="deck_collaborators"
    )

    # Reverse relations
    cards: fields.ReverseRelation["DeckCard"]

    class Meta:
        table = "decks"


class DeckCard(Model):
    id = fields.IntField(pk=True)
    deck = fields.ForeignKeyField("models.Deck", related_name="cards")
    card = fields.ForeignKeyField("models.Card", related_name="deck_entries")
    quantity = fields.IntField(default=1)
    board = fields.CharField(max_length=20, default="main")  # main, side, commander

    class Meta:
        table = "deck_cards"
        unique_together = (("deck", "card", "board"),)
