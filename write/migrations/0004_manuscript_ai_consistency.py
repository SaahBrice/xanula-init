from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("write", "0003_manuscript_book_intelligence"),
    ]

    operations = [
        migrations.AddField(
            model_name="manuscript",
            name="ai_consistency",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
