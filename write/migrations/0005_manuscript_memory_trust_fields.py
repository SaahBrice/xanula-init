from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("write", "0004_manuscript_ai_consistency"),
    ]

    operations = [
        migrations.AddField(
            model_name="manuscript",
            name="ai_memory_meta",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="manuscript",
            name="ai_chapter_memory",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="manuscript",
            name="ai_cost_mode",
            field=models.CharField(default="balanced", max_length=20),
        ),
    ]
