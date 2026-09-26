from django.db import migrations


def migrate_specific_read_state(apps, schema_editor):
    Notification = apps.get_model("notifications", "Notification")
    NotificationReadReceipt = apps.get_model("notifications", "NotificationReadReceipt")
    receipts = [
        NotificationReadReceipt(notification_id=notification.id, user_id=notification.recipient_id)
        for notification in Notification.objects.filter(
            broadcast_scope="SPECIFIC_USER", read=True, recipient_id__isnull=False
        ).iterator()
    ]
    NotificationReadReceipt.objects.bulk_create(receipts, ignore_conflicts=True)


class Migration(migrations.Migration):
    dependencies = [("notifications", "0002_notificationreadreceipt")]

    operations = [migrations.RunPython(migrate_specific_read_state, migrations.RunPython.noop)]
