from django.contrib.auth.models import User
from django.db import models

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    first_name = models.CharField(max_length=50, blank=True)
    last_name = models.CharField(max_length=50, blank=True)
    city = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    date_of_birth = models.DateField(blank=True, null=True)
    bio = models.TextField(blank=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    terms_accepted = models.BooleanField(default=False)
    # Можно добавить другие поля: дата рождения, город и т.д.

    def __str__(self):
        return self.user.username

class Generation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='generations', null=True, blank=True)
    platform = models.CharField(max_length=50)
    template_type = models.CharField(max_length=50)
    tone = models.CharField(max_length=50)
    topic = models.TextField()
    result = models.TextField()
    image_url = models.CharField(max_length=512, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username if self.user else 'Аноним'}: {self.topic[:30]}..."

