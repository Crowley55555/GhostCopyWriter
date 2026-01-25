# Generated manually to remove legacy token fields
# These fields are no longer used in the new token-based system
# Fields: daily_generations_left, generations_reset_date

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('generator', '0015_remove_unused_userprofile_fields'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='temporaryaccesstoken',
            name='daily_generations_left',
        ),
        migrations.RemoveField(
            model_name='temporaryaccesstoken',
            name='generations_reset_date',
        ),
    ]
