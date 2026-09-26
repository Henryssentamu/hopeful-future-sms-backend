from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("academics", "0001_initial")]

    operations = [
        migrations.AddConstraint(
            model_name="resultwindow",
            constraint=models.UniqueConstraint(
                fields=("result_type", "term", "year"),
                name="unique_result_window_scope",
            ),
        ),
    ]
