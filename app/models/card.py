from tortoise import fields
from tortoise.models import Model


class Card(Model):
    scryfall_id = fields.CharField(max_length=36, pk=True)
    name = fields.CharField(max_length=255, index=True)
    mana_cost = fields.CharField(max_length=100, null=True)
    cmc = fields.FloatField(default=0)
    type_line = fields.CharField(max_length=255, null=True)
    oracle_text = fields.TextField(null=True)
    colors = fields.JSONField(default=list)
    color_identity = fields.JSONField(default=list)
    set_code = fields.CharField(max_length=10, null=True)
    set_name = fields.CharField(max_length=255, null=True)
    collector_number = fields.CharField(max_length=20, null=True)
    rarity = fields.CharField(max_length=20, null=True)
    image_uri_small = fields.CharField(max_length=500, null=True)
    image_uri_normal = fields.CharField(max_length=500, null=True)
    image_uri_large = fields.CharField(max_length=500, null=True)
    power = fields.CharField(max_length=10, null=True)
    toughness = fields.CharField(max_length=10, null=True)
    loyalty = fields.CharField(max_length=10, null=True)
    layout = fields.CharField(max_length=50, null=True)
    card_faces = fields.JSONField(null=True)  # For double-faced cards
    legalities = fields.JSONField(default=dict)
    finishes = fields.JSONField(default=list)  # e.g. ["nonfoil", "foil"] or ["nonfoil", "etched"]

    # Reverse relations
    collection_entries: fields.ReverseRelation["UserCollection"]
    deck_entries: fields.ReverseRelation["DeckCard"]

    class Meta:
        table = "cards"


class UserCollection(Model):
    id = fields.IntField(pk=True)
    user = fields.ForeignKeyField("models.User", related_name="collection")
    collection = fields.ForeignKeyField("models.Collection", related_name="entries")
    card = fields.ForeignKeyField("models.Card", related_name="collection_entries")
    quantity = fields.IntField(default=1)
    finish = fields.CharField(max_length=20, default="nonfoil")  # nonfoil, foil, etched, glossy
    added_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "user_collection"
        unique_together = (("collection", "card", "finish"),)
