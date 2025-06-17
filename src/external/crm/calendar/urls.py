from django.urls import path
from src.external.crm.calendar.views import (CalendarTaskListView,TaskCreateView,ProjectListView,SectionsByProjectView,DeleteTaskView)
from .views import HolidaysAPIView
urlpatterns = [
    path('tasks/', CalendarTaskListView.as_view(), name='calendar-task-list'),
     path('task-new/', TaskCreateView.as_view(), name='task-create'),
    path('projects/project-all/', ProjectListView.as_view(), name='project-list'),
    path('projects/<int:project_id>/sections/', SectionsByProjectView.as_view(), name='sections-by-project'),
    path('delete-task/<int:task_id>/', DeleteTaskView.as_view(), name='delete_task'),
    path('holidays/', HolidaysAPIView.as_view(), name='holidays-api'),
]