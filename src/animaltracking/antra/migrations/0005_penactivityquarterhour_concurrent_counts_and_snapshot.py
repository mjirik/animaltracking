from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("antra", "0004_penactivityquarterhour"),
    ]

    operations = [
        migrations.AddField(
            model_name="penactivityquarterhour",
            name="concurrent_count_histogram_json",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="penactivityquarterhour",
            name="concurrent_count_max",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="penactivityquarterhour",
            name="concurrent_count_mean",
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name="penactivityquarterhour",
            name="concurrent_count_mode",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="penactivityquarterhour",
            name="sample_count",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="penactivityquarterhour",
            name="snapshot_captured_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="penactivityquarterhour",
            name="snapshot_relative_path",
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
