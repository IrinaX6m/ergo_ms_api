from django.urls import path
from src.external.crm.generationCommand.views import AllUsersAcademicPerformanceView,OptimalTeamFormationView

urlpatterns = [
        path('grade_users/', AllUsersAcademicPerformanceView.as_view(), name='grade-users'),
        path('optimal_team/', OptimalTeamFormationView.as_view(), name='optimal-team'),


]