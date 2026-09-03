from django.contrib import admin

from .models import Activity, AcademicPeriod, SchoolInfo

admin.site.register(SchoolInfo)
admin.site.register(AcademicPeriod)
admin.site.register(Activity)
