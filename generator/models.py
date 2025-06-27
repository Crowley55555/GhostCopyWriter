from django.db import models

class Generation(models.Model):
    platform = models.CharField(max_length=50)
    template_type = models.CharField(max_length=50)
    tone = models.CharField(max_length=50)
    topic = models.TextField()
    result = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

