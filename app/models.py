from tortoise import fields, models

class TimestampMixin:
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

class Restaurant(TimestampMixin, models.Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=200, index=True)
    location = fields.TextField(null=True)
    source_url = fields.TextField(null=True)
    favourited = fields.BooleanField(default=False)
    visited = fields.BooleanField(default=False)   
    tags = fields.JSONField(default=list)           

    class Meta:
        table = "restaurants"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name