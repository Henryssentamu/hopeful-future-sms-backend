from django.contrib import admin

from .models import (
    ClassSubjectAssignment,
    Department,
    ReportCardConfig,
    ResultWindow,
    SchoolClass,
    Subject,
    SubjectPaper,
    TeacherAssignment,
)

admin.site.register(Subject)
admin.site.register(SubjectPaper)
admin.site.register(Department)
admin.site.register(SchoolClass)
admin.site.register(ClassSubjectAssignment)
admin.site.register(TeacherAssignment)
admin.site.register(ReportCardConfig)
admin.site.register(ResultWindow)
