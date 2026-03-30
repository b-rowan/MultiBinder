from tortoise import fields
from tortoise.models import Model


class Collection(Model):
    id = fields.IntField(pk=True)
    user = fields.ForeignKeyField("models.User", related_name="collections")
    name = fields.CharField(max_length=255)
    description = fields.TextField(default="")
    type = fields.CharField(max_length=20, default="personal")  # personal, external
    external_source = fields.CharField(max_length=50, null=True)  # moxfield
    external_url = fields.CharField(max_length=500, null=True)
    last_synced = fields.DatetimeField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "collections"