from django.urls import path
from src.external.expsys_module.views import PostCompetenciesandVacations
from src.external.expsys_module.views import  TeacherSubjectsView,SubjectCreateView,SubjectIndicatorsCompetenciesView,CompetenciesView,IndicatorSubjectsCountView,IndicatorsView,CompetenceCreateView,IndicatorCreateView,CompetenceIndicatorsView,DeleteSubject
from src.external.expsys_module.views import DeleteCompetence,DeleteIndicator,StudentGradesView,CompetenceMasteryAllStudentsView,UpdateSubjectView,UpdateCompetenceView,UpdateIndicatorView, SubjectStudentCountView, SubjectLessonCountView,SubjectTestCountView


urlpatterns = [
     path('post-competencies-vacations', PostCompetenciesandVacations.as_view(), name='post competencies and vacations'),
     path('subjects-all/', TeacherSubjectsView.as_view(), name='subjects-all'),
     path('subject-create/', SubjectCreateView.as_view(), name='subject-create'),
     path('subjectsindicators/', SubjectIndicatorsCompetenciesView.as_view(), name='subjectsindicators'),
     path('delete-subject/<int:subject_id>/',DeleteSubject.as_view(), name='delete_subject'),
     path('allcompetencies/', CompetenciesView.as_view(), name='allcompetencies'),
     path('indicator-subjects-count/', IndicatorSubjectsCountView.as_view(), name='indicator-subjects-count'),
     path('allindicators/', IndicatorsView.as_view(), name='allindicators'),
     path('competence-create/', CompetenceCreateView.as_view(), name='competence-create'),
     path('indicator-create/', IndicatorCreateView.as_view(), name='indicator-create'),
     path('competenceindicators/', CompetenceIndicatorsView.as_view(), name='competenceindicators'),
     path('delete-competence/<int:competence_id>/',DeleteCompetence.as_view(), name='delete_competence'),
     path('delete-indicator/<int:indicator_id>/',DeleteIndicator.as_view(), name='delete_indicator'),
     path('information/', StudentGradesView.as_view(), name='information'),
     path('information-competence/', CompetenceMasteryAllStudentsView.as_view(), name='information_competence'),
     path('update-subject/<int:subject_id>/',UpdateSubjectView.as_view(), name='update_subject'),
     path('update-competence/<int:competence_id>/',UpdateCompetenceView.as_view(), name='update_competence'),
     path('update-indicator/<int:indicator_id>/',UpdateIndicatorView.as_view(), name='update_indicator'),
     path('countstudents-subject/', SubjectStudentCountView.as_view(), name='countstudents_subject'),
     path('countlessons-subject/',SubjectLessonCountView.as_view(), name='countlessons_subject'),
     path('counttests-subject/',SubjectTestCountView.as_view(), name='counttests_subject'),


]