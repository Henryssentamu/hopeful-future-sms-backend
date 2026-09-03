from django.contrib import admin

from .models import TimetableConfig, TimetablePeriod, TimetableSlot

admin.site.register(TimetableConfig)
admin.site.register(TimetablePeriod)
admin.site.register(TimetableSlot)
