from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("staff", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="recruitmentrecord",
            name="hired_user",
            field=models.OneToOneField(
                blank=True, editable=False, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="recruitment_record", to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
