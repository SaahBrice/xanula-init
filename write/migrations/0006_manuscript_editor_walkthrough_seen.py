from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("write", "0005_manuscript_memory_trust_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="manuscript",
            name="editor_walkthrough_seen",
            field=models.BooleanField(default=False),
        ),
    ]
