from django.contrib import admin

from .models import BiometricLog, NonTeachingStaff, RecruitmentRecord, Teacher

admin.site.register(Teacher)
admin.site.register(NonTeachingStaff)
admin.site.register(RecruitmentRecord)
admin.site.register(BiometricLog)
