from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from src.core.utils.database.base import SqlAlchemyManager
from src.core.utils.database.dbconfig import DBConfig
from src.core.utils.database.main import OrderedDictQueryExecutor
from src.core.utils.management.commands.add_module import Command
from django.contrib.auth import authenticate
from django.utils.crypto import get_random_string
from rest_framework.views import APIView
import logging
from django.contrib.auth.models import User

from src.core.utils.methods import (
    parse_errors_to_dict, 
    send_confirmation_email
)
from src.core.cms.adp.models import EmailConfirmationCode
from src.core.cms.adp.serializers import (
    UserLoginSerializer, 
    UserRegistrationSerializer,
    UserRegistrationValidationSerializer,
)
from src.core.utils.base.base_views import BaseAPIView
from src.core.cms.queries import (get_users_permissions, get_users_group, get_users_group_permissions)
import requests
from rest_framework.request import Request
import pandas as pd
from src.external.expsys_module.models import (Skill, Vacance)
from django.db import IntegrityError, connection
from src.external.lms.models import Subject,Grade,Lesson, Theme,Test
from src.external.expsys_module.models import Competence,Indicator_Subject,Indicator,Indicator_Competence
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Count

from django.db import transaction
from django.shortcuts import get_object_or_404

User = get_user_model()

class TeacherSubjectsView(APIView):
    @swagger_auto_schema(
        operation_description="Получение всех предметов по ID учителя из query-параметра",
        manual_parameters=[
            openapi.Parameter(
                'user_id', openapi.IN_QUERY, description="ID пользователя", type=openapi.TYPE_INTEGER, required=True
            )
        ],
        responses={
            200: openapi.Response(
                description="Список предметов учителя",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'data': openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            items=openapi.Schema(
                                type=openapi.TYPE_OBJECT,
                                properties={
                                    'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                                    'name': openapi.Schema(type=openapi.TYPE_STRING),
                                    'description': openapi.Schema(type=openapi.TYPE_STRING),
                                    'creationdate': openapi.Schema(type=openapi.TYPE_STRING, format='date'),
                                    'lastupdate': openapi.Schema(type=openapi.TYPE_STRING, format='date-time'),
                                    'teacher_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                                }
                            )
                        ),
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                    }
                )
            ),
            400: "Неверный запрос",
            404: "Пользователь не найден",
            403: "Пользователь не является учителем",
            500: "Внутренняя ошибка сервера"
        }
    )
    def get(self, request):
        try:
            user_id = request.query_params.get('user_id')

            if not user_id:
                return Response(
                    {"error": "user_id обязателен", "message": "Укажите ID пользователя в параметрах запроса."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return Response(
                    {"error": "Пользователь не найден", "message": f"Пользователь с ID {user_id} не существует."},
                    status=status.HTTP_404_NOT_FOUND
                )


            teacher_subjects = Subject.objects.filter(teacher=user)

            subjects_data = [{
                'id': subject.id,
                'name': subject.name,
                'description': subject.description,
                'creationdate': subject.creationdate,
                'lastupdate': subject.lastupdate,
                'teacher_id': subject.teacher.id,
            } for subject in teacher_subjects]

            return Response(
                {
                    "data": subjects_data,
                    "message": f"Найдено {len(subjects_data)} предметов."
                },
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return Response(
                {"error": str(e), "message": "Ошибка при получении предметов."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


logger = logging.getLogger(__name__)


class SubjectCreateView(APIView):
    def post(self, request):
        try:
            # Валидация данных
            name = request.data.get('name', '').strip()
            description = request.data.get('description', '').strip()

            if not name:
                return Response(
                    {
                        "message": "Название предмета обязательно"
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Проверка на авторизацию
            if not request.user.is_authenticated:
                return Response(
                    {
                        "message": "Требуется авторизация"
                    },
                    status=status.HTTP_401_UNAUTHORIZED
                )

            # Создание предмета
            subject = Subject.objects.create(
                name=name,
                description=description,
                teacher=request.user
            )

            # Формирование успешного ответа
            return Response(
                {
                    "id": subject.id,
                    "name": subject.name,
                    "description": subject.description,
                    "teacher_id": subject.teacher.id,
                    "creation_date": subject.creationdate.strftime('%Y-%m-%d'),
                    "icon": "book",
                    "icon_background": "bg-blue",
                    "stats": {
                        "students": 0,
                        "lessons": 0,
                        "tasks": 0
                    }
                },
                status=status.HTTP_201_CREATED  # будет считаться успешным, если handleResponse проверяет только 200
            )

        except Exception as e:
            # Логирование исключений
            logger.error(f"Ошибка при создании предмета: {str(e)}")
            return Response(
                {
                    "message": "Внутренняя ошибка сервера",
                    "details": str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class SubjectIndicatorsCompetenciesView(APIView):
    @swagger_auto_schema(
        operation_description="Получение всех компетенций выбранного предмета",
        manual_parameters=[
            openapi.Parameter(
                'subject_id',
                openapi.IN_QUERY,
                description="ID предмета",
                type=openapi.TYPE_INTEGER
            )
        ],
        responses={
            200: "Список компетенций предмета.",
            400: "Ошибка при выполнении запроса.",
            500: "Внутренняя ошибка сервера."
        }
    )
    def get(self, request):
        try:
            subject_id = request.GET.get('subject_id')
            
            if not subject_id:
                return Response(
                    {"error": "Не указан ID предмета", "message": "Необходимо указать subject_id"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Получаем все связи компетенций с предметом
            competence_links = Indicator_Subject.objects.filter(
                subject_id=subject_id
            ).select_related('indicator')

            competencies_data = []
            for link in competence_links:
                competence_data = {
                    'id': link.indicator.id,
                    'name': link.indicator.name,
                    'description':link.indicator.description,
                    'sat_coef': link.sat_coef,
                    'subject_id': link.subject_id,
                    'knowledge':link.knowledge,
                    'ability':link.ability,
                    'mastered':link.mastered,
                }
                competencies_data.append(competence_data)

            return Response(
                {
                    "data": competencies_data,
                    "message": "Компетенции предмета успешно получены.",
                    "count": len(competencies_data)
                },
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {"error": str(e), "message": "Ошибка при получении компетенций предмета."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class CompetenciesView(APIView):
    @swagger_auto_schema(
        operation_description="Получение всех имеющихся компетенций",
        responses={
            200: "Список компетенций.",
            400: "Ошибка при выполнении запроса.",
            500: "Внутренняя ошибка сервера."
        }
    )
    def get(self, request):
        try:            
            # Получаем все компетенции
            competencies = Competence.objects.all()
            competencies_data = []
            for comp in competencies:
                competence_data = {
                    'id': comp.id,
                    'name': comp.name,
                    'description':comp.description,
                    'category':comp.category,
                }
                competencies_data.append(competence_data)

            return Response(
                {
                    "data": competencies_data,
                    "message": "Компетенции успешно получены.",
                    "count": len(competencies_data)
                },
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {"error": str(e), "message": "Ошибка при получении компетенций."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class IndicatorsView(APIView):
    @swagger_auto_schema(
        operation_description="Получение всех имеющихся индикаторов компетенций",
        responses={
            200: "Список индикаторов.",
            400: "Ошибка при выполнении запроса.",
            500: "Внутренняя ошибка сервера."
        }
    )
    def get(self, request):
        try:            
            # Получаем все индикаторы
            indicators = Indicator.objects.all()
            indicators_data = []
            for ind in indicators:
                indicator_data = {
                    'id': ind.id,
                    'name': ind.name,
                    'description':ind.description,
                    'category':ind.category
                }
                indicators_data.append(indicator_data)

            return Response(
                {
                    "data": indicators_data,
                    "message": "Индикаторы успешно получены.",
                    "count": len(indicators_data)
                },
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {"error": str(e), "message": "Ошибка при получении индикаторов."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class IndicatorSubjectsCountView(APIView):
    @swagger_auto_schema(
        operation_description="Получение количества предметов по ID индикатора компетенции",
        manual_parameters=[
            openapi.Parameter(
                'indicator_id', openapi.IN_QUERY, 
                description="ID индикатора компетенции", 
                type=openapi.TYPE_INTEGER, 
                required=True
            )
        ],
        responses={
            200: openapi.Response(
                description="Количество предметов с указанным индикатором",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'subjects_count': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                    }
                )
            ),
            400: "Неверный запрос",
            404: "Индикатор не найден",
            500: "Внутренняя ошибка сервера"
        }
    )
    def get(self, request):
        try:
            indicator_id = request.query_params.get('indicator_id')

            if not indicator_id:
                return Response(
                    {"error": "indicator_id обязателен", "message": "Укажите ID индикатора в параметрах запроса."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                indicator = Indicator.objects.get(id=indicator_id)
            except Indicator.DoesNotExist:
                return Response(
                    {"error": "Индикатор не найден", "message": f"Индикатор с ID {indicator_id} не существует."},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Подсчет количества предметов с этим индикатором
            count = Indicator_Subject.objects.filter(indicator=indicator).count()

            return Response(
                {
                    "subjects_count": count,
                    "message": f"Найдено {count} предметов с этим индикатором."
                },
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return Response(
                {"error": str(e), "message": "Ошибка при получении данных."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class CompetenceCreateView(APIView):
    def post(self, request):
        try:
            # Валидация данных
            name = request.data.get('name', '').strip()
            description = request.data.get('description', '').strip()
            category=request.data.get('category', '').strip()
            if not name:
                return Response(
                    {
                        "message": "Название компетенции обязательно"
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Проверка на существующую компетенцию с таким именем
            if Competence.objects.filter(name=name).exists():
                return Response(
                    {
                        "message": "Компетенция с таким названием уже существует"
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Создание компетенции (без указания id, чтобы БД сама сгенерировала новый)
            competence = Competence.objects.create(
                name=name,
                description=description,
                category=category
            )

            # Формирование успешного ответа
            return Response(
                {
                    "id": competence.id,
                    "name": competence.name,
                    "description": competence.description,
                    "category":competence.category,
                },
                status=status.HTTP_201_CREATED
            )

        except IntegrityError as e:
            logger.error(f"Ошибка целостности при создании компетенции: {str(e)}")
            return Response(
                {
                    "message": "Ошибка при создании компетенции (проблема с уникальностью данных)",
                    "details": str(e)
                },
                status=status.HTTP_400_BAD_REQUEST
            )
            
        except Exception as e:
            # Логирование исключений
            logger.error(f"Ошибка при создании компетенции: {str(e)}")
            return Response(
                {
                    "message": "Внутренняя ошибка сервера",
                    "details": str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class IndicatorCreateView(APIView):
    def post(self, request):
        try:
            # Валидация данных
            name = request.data.get('name', '').strip()
            description = request.data.get('description', '').strip()
            category = request.data.get('category', '').strip()


            if not name:
                return Response(
                    {
                        "message": "Название индикатора обязательно"
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Проверка на существующую компетенцию с таким именем
            if Indicator.objects.filter(name=name).exists():
                return Response(
                    {
                        "message": "Индикатор с таким названием уже существует"
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            indicator = Indicator.objects.create(
                name=name,
                description=description,
                category=category,
            )

            # Формирование успешного ответа
            return Response(
                {
                    "id": indicator.id,
                    "name": indicator.name,
                    "description": indicator.description,
                    "category": indicator.category,

                    
                },
                status=status.HTTP_201_CREATED
            )

        except IntegrityError as e:
            logger.error(f"Ошибка целостности при создании компетенции: {str(e)}")
            return Response(
                {
                    "message": "Ошибка при создании компетенции (проблема с уникальностью данных)",
                    "details": str(e)
                },
                status=status.HTTP_400_BAD_REQUEST
            )
            
        except Exception as e:
            # Логирование исключений
            logger.error(f"Ошибка при создании индикатора: {str(e)}")
            return Response(
                {
                    "message": "Внутренняя ошибка сервера",
                    "details": str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
class CompetenceIndicatorsView(APIView):
    @swagger_auto_schema(
        operation_description="Получение всех индикаторов в компитенции",
        manual_parameters=[
            openapi.Parameter(
                'competence_id',
                openapi.IN_QUERY,
                description="ID компитенции",
                type=openapi.TYPE_INTEGER
            )
        ],
        responses={
            200: "Список индикаторов компитенции.",
            400: "Ошибка при выполнении запроса.",
            500: "Внутренняя ошибка сервера."
        }
    )
    def get(self, request):
        try:
            competence_id = request.GET.get('competence_id')
            
            if not competence_id:
                return Response(
                    {"error": "Не указан ID компитенции", "message": "Необходимо указать competence_id"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Получаем все связи индикаторов с компитенцией
            indicator_links = Indicator_Competence.objects.filter(
                competence_id=competence_id
            ).select_related('indicator')

            indicators_data = []
            for link in indicator_links:
                indicator_data = {
                    'id': link.indicator.id,
                    'name': link.indicator.name,
                    'description':link.indicator.description,
                }
                indicators_data.append(indicator_data)

            return Response(
                {
                    "data": indicators_data,
                    "message": "Индикаторы компитенций успешно получены.",
                    "count": len(indicators_data)
                },
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {"error": str(e), "message": "Ошибка при получении индикаторов компитенции."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class PostCompetenciesandVacations(BaseAPIView):
    permission_classes = [IsAuthenticated]
    @swagger_auto_schema(
        operation_description="Запись компетенций и вакансий.",
        responses={
            200: "компетенции записаны",
            401: "Не удалось записать компетенции"
        },
    )
    def post(self, request: Request):
        url = "https://api.hh.ru/vacancies?per_page=100&experience=noExperience&text=Программист"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            vacancies = data.get('items', [])
            df = pd.DataFrame(vacancies).iloc[:, 0].tolist()
            allcompec = []
            for id in df:
                urltemp = "https://api.hh.ru/vacancies/"+id
                responset = requests.get(urltemp)
                if response.status_code == 200:
                    data = responset.json()
                    t = data['key_skills']
                    l = []
                    for i in t:
                        l.append(i['name'])
                    allcompec.append(l)
            uniquecompecs =[]
            for com in allcompec:
                for par in com:
                    if uniquecompecs.count(par)==0:
                        uniquecompecs.append(par)
            uniquecompecs.sort()
            dictlist =[]
            key =['name']
            for i in range(0,len(uniquecompecs)):
                dictlist.append(dict.fromkeys(key,uniquecompecs[i]))
            table_name = Skill._meta.db_table
            with connection.cursor() as cursor:
                cursor.execute(f"TRUNCATE TABLE {table_name} RESTART IDENTITY CASCADE;")
            for item in dictlist:
                Skill.objects.create(**item)
            df = pd.DataFrame(vacancies)
            vacancies_df = df['name'].to_frame()
            salary = df['salary'].apply(pd.Series)
            area = df['area'].apply(pd.Series)
            types = df['type'].apply(pd.Series)
            experience = df['experience'].apply(pd.Series)
            employment = df['employment'].apply(pd.Series)
            vacancies_df['salary_from'] = salary['from']
            vacancies_df['salary_to'] = salary['to']
            vacancies_df['currency'] = salary['currency']
            vacancies_df['area'] = area['name']
            vacancies_df['type'] = types['name']
            vacancies_df['employment'] = employment['name']
            vacancies_df['experience'] = experience['name']
            sck = pd.DataFrame({'Compec': allcompec})
            records = vacancies_df.to_dict('records')
            sck = sck.to_dict('records')
            table_name = Vacance._meta.db_table
            with connection.cursor() as cursor:
                cursor.execute(f"TRUNCATE TABLE {table_name} RESTART IDENTITY CASCADE;")
            for item in records:
                Vacance.objects.create(**item)
            for i in range(0, len(sck)):
                vac = Vacance.objects.get(id=i+1)
                for item in sck[i]['Compec']:
                    skill = Skill.objects.get(name=item)
                    vac.skill.add(skill)
            return Response(
            uniquecompecs,
            status=status.HTTP_200_OK
        )

class DeleteSubject(APIView):
    @transaction.atomic
    def delete(self, request, subject_id):  # Изменил task_id на id
        print("dada")
        try:
            print(subject_id)
            #subject = get_object_or_404(Subject, id=subject_id)  # Используем переданный id
            subject = Subject.objects.get(id=subject_id)
            subject.delete()
            #subject.save()
            
            return Response(
                {"success": True, "message": "Предмет удален"},
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            print(e)
            return Response(
                {
                    "success": False,
                    "error": str(e),
                    "message": "Ошибка при удалении предмета"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
class DeleteCompetence(APIView):
    @transaction.atomic
    def delete(self, request, competence_id):  # Изменил task_id на id
        print("dada")
        try:
            print(id)
            competence = get_object_or_404(Competence, id=competence_id)  # Используем переданный id
            competence.delete()
            
            return Response(
                {"success": True, "message": "Компетенция удалена"},
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            return Response(
                {
                    "success": False,
                    "error": str(e),
                    "message": "Ошибка при удалении компетенции"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class DeleteIndicator(APIView):
    @transaction.atomic
    def delete(self, request, indicator_id):  # Изменил task_id на id
        print("dada")
        try:
            print(id)
            indicator = get_object_or_404(Indicator, id=indicator_id)  # Используем переданный id
            indicator.delete()
            
            return Response(
                {"success": True, "message": "Индикатор компетенции удален"},
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            return Response(
                {
                    "success": False,
                    "error": str(e),
                    "message": "Ошибка при удалении индикатора компетенции"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class StudentGradesView(APIView):
    def get(self, request):
        try:
            student_id = request.query_params.get('student_id')
            subject_id = request.query_params.get('subject_id')
            
            grades_query = Grade.objects.all()
            
            if student_id:
                grades_query = grades_query.filter(student_id=student_id)
            
            if subject_id:
                grades_query = grades_query.filter(subject_id=subject_id)
            
            grades_data = []
            
            for grade in grades_query:
                student = grade.student
                grades_data.append({
                    "student_id": student.id,
                    "student_fio": f"{student.last_name} {student.first_name}".strip(),
                    "subject_id": grade.subject.id,
                    "subject_name": grade.subject.name,
                    "grade": grade.grade,
                    "grade_date": grade.related,
                    "last_update": grade.lastupdate
                })
            
            return Response(
                {
                    "success": True,
                    "message": "Данные об оценках успешно получены",
                    "grades": grades_data
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            return Response(
                {
                    "success": False,
                    "error": str(e),
                    "message": "Ошибка при получении данных об оценках"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
class CompetenceMasteryAllStudentsView(APIView):
    def get(self, request):
        try:
            competence_id = request.query_params.get('competence_id')
            
            if not competence_id:
                return Response(
                    {
                        "success": False,
                        "message": "Необходимо указать competence_id"
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            competence = get_object_or_404(Competence, id=competence_id)
            
            # Получаем все индикаторы для данной компетенции через промежуточную модель
            indicator_competences = Indicator_Competence.objects.filter(competence=competence)
            indicators_count = indicator_competences.count()
            
            if indicators_count == 0:
                return Response(
                    {
                        "success": False,
                        "message": "Для данной компетенции не найдены индикаторы"
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
            
            base_coef = 100 / indicators_count
            students_data = []
            
            # Получаем всех студентов, у которых есть оценки по предметам этой компетенции
            # Через связи: Competence -> Indicator_Competence -> Indicator -> Indicator_Subject -> Subject -> Grade
            students_with_grades = User.objects.filter(
                grade__subject__indicator_subject__indicator__indicator_competence__competence=competence
            ).distinct()
            
            for student in students_with_grades:
                total_mastery = 0
                subjects_data = []
                
                # Для каждого индикатора компетенции
                for ic in indicator_competences:
                    indicator = ic.indicator
                    
                    # Получаем связанные предметы через Indicator_Subject
                    indicator_subjects = Indicator_Subject.objects.filter(indicator=indicator)
                    
                    for isub in indicator_subjects:
                        subject = isub.subject
                        
                        # Получаем последнюю оценку студента по этому предмету
                        grade = Grade.objects.filter(
                            student=student,
                            subject=subject
                        ).order_by('-related').first()
                        
                        if grade:
                            mastery_contribution = (base_coef * grade.grade) / 100
                            total_mastery += mastery_contribution
                            
                            subjects_data.append({
                                "subject_id": subject.id,
                                "subject_name": subject.name,
                                "indicator_id": indicator.id,
                                "indicator_name": indicator.name,
                                "grade": grade.grade,
                                "mastery_contribution": mastery_contribution,
                                "grade_date": grade.related.strftime('%Y-%m-%d') if grade.related else None
                            })
                
                # Округляем общий уровень освоения
                total_mastery = round(total_mastery, 2)
                
                students_data.append({
                    "student_id": student.id,
                    "student_fio": f"{student.last_name} {student.first_name}".strip(),
                    "total_mastery": total_mastery,
                    "subjects": subjects_data
                })
            
            # Сортируем студентов по уровню освоения (от большего к меньшему)
            students_data.sort(key=lambda x: x['total_mastery'], reverse=True)
            
            # Рассчитываем средний уровень освоения по всем студентам
            avg_mastery = round(
                sum(s['total_mastery'] for s in students_data) / len(students_data) if students_data else 0,
                2
            )
            
            return Response(
                {
                    "success": True,
                    "message": "Данные об освоении компетенции для всех студентов успешно получены",
                    "data": {
                        "competence_id": competence.id,
                        "competence_name": competence.name,
                        "indicators_count": indicators_count,
                        "average_mastery": avg_mastery,
                        "students": students_data
                    }
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            return Response(
                {
                    "success": False,
                    "error": str(e),
                    "message": "Ошибка при расчете уровня освоения компетенции"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class UpdateSubjectView(APIView):
    @transaction.atomic
    def post(self, request, subject_id):
        try:
            subject = get_object_or_404(Subject, id=subject_id)
            
            # Обновляем поля предмета из данных запроса
            fields_to_update = {
                'name': 'name',
                'description': 'description',
                'teacher': 'teacher_id'  # Обработка ForeignKey отдельно
            }
            
            for field, model_field in fields_to_update.items():
                if field in request.data:
                    # Особое поле для обработки ForeignKey
                    if field == 'teacher':
                        teacher_id = request.data[field]
                        teacher = get_object_or_404(User, id=teacher_id)
                        setattr(subject, model_field, teacher)
                    else:
                        setattr(subject, model_field, request.data[field])
            
            # Обновляем дату последнего изменения
            subject.lastupdate = timezone.now()
            subject.save()
            
            return Response(
                {
                    "success": True,
                    "message": "Предмет успешно обновлен",
                    "subject": {
                        "id": subject.id,
                        "name": subject.name,
                        "description": subject.description,
                        "creationdate": subject.creationdate,
                        "lastupdate": subject.lastupdate,
                        "teacher": {
                            "id": subject.teacher.id,
                            "username": subject.teacher.username,
                            "full_name": f"{subject.teacher.last_name} {subject.teacher.first_name}"
                        }
                    }
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            return Response(
                {
                    "success": False,
                    "error": str(e),
                    "message": "Ошибка при обновлении предмета"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class UpdateCompetenceView(APIView):
    @transaction.atomic
    def post(self, request, competence_id):
        try:
            competence = get_object_or_404(Competence, id=competence_id)
            
            # Обновляем поля компетенции из данных запроса
            fields_to_update = {
                'name': 'name',
                'description': 'description',
                'category': 'category'
            }
            
            for field, model_field in fields_to_update.items():
                if field in request.data:
                    setattr(competence, model_field, request.data[field])
            
            competence.save()
            
            return Response(
                {
                    "success": True,
                    "message": "Компетенция успешно обновлена",
                    "competence": {
                        "id": competence.id,
                        "name": competence.name,
                        "description": competence.description,
                        "category": competence.category
                    }
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            return Response(
                {
                    "success": False,
                    "error": str(e),
                    "message": "Ошибка при обновлении компетенции"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class UpdateIndicatorView(APIView):
    @transaction.atomic
    def post(self, request, indicator_id):
        try:
            indicator = get_object_or_404(Indicator, id=indicator_id)
            
            # Обновляем поля индикатора из данных запроса
            fields_to_update = {
                'name': 'name',
                'description': 'description',
                'category':'category'
            }
            
            for field, model_field in fields_to_update.items():
                if field in request.data:
                    setattr(indicator, model_field, request.data[field])
            
            indicator.save()
            
            return Response(
                {
                    "success": True,
                    "message": "Индикатор успешно обновлен",
                    "indicator": {
                        "id": indicator.id,
                        "name": indicator.name,
                        "description": indicator.description,
                        "category":indicator.category,
                    }
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            return Response(
                {
                    "success": False,
                    "error": str(e),
                    "message": "Ошибка при обновлении индикатора"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class SubjectStudentCountView(APIView):
    def get(self, request):
        try:
            subject_id = request.query_params.get('subject_id')
            
            if not subject_id:
                return Response(
                    {
                        "success": False,
                        "message": "Не указан ID предмета"
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Получаем количество уникальных студентов по предмету
            student_count = Grade.objects.filter(subject_id=subject_id)\
                                      .values('student')\
                                      .distinct()\
                                      .count()
            
            # Дополнительно получаем информацию о предмете
            subject = Subject.objects.get(id=subject_id)
            
            return Response(
                {
                    "success": True,
                    "message": "Количество студентов по предмету успешно получено",
                    "data": {
                        "subject_id": subject.id,
                        "subject_name": subject.name,
                        "student_count": student_count,
                        "teacher_id": subject.teacher.id,
                        "teacher_name": f"{subject.teacher.last_name} {subject.teacher.first_name}".strip()
                    }
                },
                status=status.HTTP_200_OK
            )
            
        except Subject.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "message": "Предмет не найден"
                },
                status=status.HTTP_404_NOT_FOUND
            )
            
        except Exception as e:
            return Response(
                {
                    "success": False,
                    "error": str(e),
                    "message": "Ошибка при получении количества студентов"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class SubjectLessonCountView(APIView):
    def get(self, request):
        try:
            subject_id = request.query_params.get('subject_id')
            
            if not subject_id:
                return Response(
                    {
                        "success": False,
                        "message": "Не указан ID предмета"
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Получаем количество уникальных уроков по предмету
            lesson_count = Lesson.objects.filter(theme__subject_id=subject_id)\
                                      .values('id')\
                                      .distinct()\
                                      .count()
            
            # Дополнительно получаем информацию о предмете
            subject = Subject.objects.get(id=subject_id)
            
            return Response(
                {
                    "success": True,
                    "message": "Количество уроков по предмету успешно получено",
                    "data": {
                        "subject_id": subject.id,
                        "subject_name": subject.name,
                        "lesson_count": lesson_count,
                        "teacher_id": subject.teacher.id,
                        "teacher_name": f"{subject.teacher.last_name} {subject.teacher.first_name}".strip()
                    }
                },
                status=status.HTTP_200_OK
            )
            
        except Subject.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "message": "Предмет не найден"
                },
                status=status.HTTP_404_NOT_FOUND
            )
            
        except Exception as e:
            return Response(
                {
                    "success": False,
                    "error": str(e),
                    "message": "Ошибка при получении количества уроков"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
class SubjectTestCountView(APIView):
    def get(self, request):
        try:
            subject_id = request.query_params.get('subject_id')
            
            if not subject_id:
                return Response(
                    {
                        "success": False,
                        "message": "Не указан ID предмета"
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Получаем количество уникальных тестов по предмету
            test_count = Test.objects.filter(
                lesson__theme__subject_id=subject_id
            ).values('id').distinct().count()
            
            # Дополнительно получаем информацию о предмете
            subject = Subject.objects.get(id=subject_id)
            
            return Response(
                {
                    "success": True,
                    "message": "Количество тестов по предмету успешно получено",
                    "data": {
                        "subject_id": subject.id,
                        "subject_name": subject.name,
                        "test_count": test_count,
                        "teacher_id": subject.teacher.id,
                        "teacher_name": f"{subject.teacher.last_name} {subject.teacher.first_name}".strip()
                    }
                },
                status=status.HTTP_200_OK
            )
            
        except Subject.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "message": "Предмет не найден"
                },
                status=status.HTTP_404_NOT_FOUND
            )
            
        except Exception as e:
            return Response(
                {
                    "success": False,
                    "error": str(e),
                    "message": "Ошибка при получении количества тестов"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )