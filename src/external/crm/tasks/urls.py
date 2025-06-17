from django.urls import path


from src.external.crm.tasks.views import SectionTaskView,SectionCreateView,TaskCreateView,DeleteTaskView,SubtaskCreateView,DeleteSectionView,ToggleTaskStatusView
from src.external.crm.tasks.views import UpdateTaskView, UpdateSectionView, TaskAssigneeView

urlpatterns = [
    path('section-tasks/', SectionTaskView.as_view(), name='section-tasks'),
    path('section-new/', SectionCreateView.as_view(), name='section_add'),
    path('task-new/', TaskCreateView.as_view(), name='task_add'),
    path('assignee/<int:task_id>/', TaskAssigneeView.as_view(), name='task-assignee'),

    path('delete-task/<int:task_id>/', DeleteTaskView.as_view(), name='delete_task'),
    path('new-subtask/', SubtaskCreateView.as_view(), name='subtask-create'),
    path('delete-section/<int:section_id>/', DeleteSectionView.as_view(), name='delete_section'),
    path('toggle-task/<int:task_id>/', ToggleTaskStatusView.as_view(), name='toggle_task'),
    path('update-task/<int:task_id>/', UpdateTaskView.as_view(), name='update_task'),
    path('update-section/<int:section_id>/',UpdateSectionView.as_view(), name='update_section'),
]

