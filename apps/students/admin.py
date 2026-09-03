from django.contrib import admin

from .models import (
    ParentInfo,
    Student,
    StudentAttendanceRecord,
    StudentSubjectEnrollment,
    TermEnrollment,
    TermRecord,
    TermSubjectMark,
)

admin.site.register(Student)
admin.site.register(ParentInfo)
admin.site.register(StudentSubjectEnrollment)
admin.site.register(TermEnrollment)
admin.site.register(TermRecord)
admin.site.register(TermSubjectMark)
admin.site.register(StudentAttendanceRecord)
