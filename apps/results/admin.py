from django.contrib import admin

from .models import ResultEntry, ResultUpload

admin.site.register(ResultUpload)
admin.site.register(ResultEntry)
