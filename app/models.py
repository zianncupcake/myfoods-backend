from tortoise.models import Model
from tortoise import fields

class User(Model):
    id = fields.IntField(pk=True)
    username = fields.CharField(max_length=50, unique=True)
    password = fields.CharField(max_length=255) 
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    items: fields.ReverseRelation["Item"]

    def __str__(self):
        return self.username

class Item(Model):
    id = fields.IntField(pk=True)
    source_url = fields.TextField(null=True) 
    image_url = fields.TextField(null=True) 
    notes = fields.TextField(null=True)
    categories = fields.JSONField(default_factory=list) 
    tags = fields.JSONField(default_factory=list)      
    creator = fields.CharField(max_length=255, null=True) 

    user: fields.ForeignKeyNullableRelation[User] = fields.ForeignKeyField(
        "models.User", related_name="items", null=False, on_delete=fields.CASCADE
    )

    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    def __str__(self):
        return self.title
