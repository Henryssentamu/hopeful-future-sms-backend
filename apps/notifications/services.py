"""Port of NotificationContext's notify* functions."""

from .models import BroadcastScope, Notification


def notify_dos(title: str, message: str) -> Notification:
    return Notification.objects.create(broadcast_scope=BroadcastScope.DOS, title=title, message=message)


def notify_teacher(user, title: str, message: str) -> Notification:
    return Notification.objects.create(recipient=user, broadcast_scope=BroadcastScope.SPECIFIC_USER, title=title, message=message)


def notify_all_teachers(title: str, message: str) -> Notification:
    return Notification.objects.create(broadcast_scope=BroadcastScope.ALL_TEACHERS, title=title, message=message)
