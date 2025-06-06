# Generated by Django 5.2.1 on 2025-05-11 22:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('profiles', '0002_profile_is_visible'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='blocked_users',
            field=models.ManyToManyField(blank=True, related_name='blocked_by', to='profiles.profile'),
        ),
        migrations.AddField(
            model_name='profile',
            name='matches',
            field=models.ManyToManyField(blank=True, related_name='matched_with', to='profiles.profile'),
        ),
    ]
