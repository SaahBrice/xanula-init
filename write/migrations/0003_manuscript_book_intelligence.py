from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("write", "0002_manuscript_ai_memory"),
    ]

    operations = [
        migrations.AddField(
            model_name="manuscript",
            name="ai_voice",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="manuscript",
            name="ai_chapter_map",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="manuscript",
            name="ai_entities",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="manuscript",
            name="ai_usage",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="manuscript",
            name="ai_memory_stale",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
