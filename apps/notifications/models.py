from django.conf import settings
from django.db import models


class BroadcastScope(models.TextChoices):
    """
    Replaces the frontend's fragile string-matched `audience` field
    ("dos"|"all-teachers"|<exact teacher name string>) with a real
    recipient FK + scope choice.
    """

    DOS = "DOS", "Director of Studies"
    ALL_TEACHERS = "ALL_TEACHERS", "All Teachers"
    SPECIFIC_USER = "SPECIFIC_USER", "Specific User"


class Notification(models.Model):
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="notifications",
        help_text="Set only when broadcast_scope=SPECIFIC_USER",
    )
    broadcast_scope = models.CharField(max_length=15, choices=BroadcastScope.choices)
    title = models.CharField(max_length=200)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class NotificationReadReceipt(models.Model):
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE, related_name="read_receipts")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notification_read_receipts")
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["notification", "user"], name="unique_notification_read_receipt"),
        ]
