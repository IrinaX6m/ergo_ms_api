from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.views import APIView
from django.db import models
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.utils import timezone
from datetime import datetime
from django.db.models import Q


from src.core.utils.database.main import OrderedDictQueryExecutor
from src.core.cms.adp.queries import (
    get_sections_and_tasks,add_new_section,add_new_task
)
from src.core.utils.base.base_views import BaseAPIView
import psycopg2
from django.db import connection
from src.external.crm.models import Section,Task

# Создавайте свои представления здесь
class SectionTaskView(APIView):
    @swagger_auto_schema(
        operation_description="Получение всех разделов и их задач с подзадачами",
        responses={
            200: "Список разделов и их задач.",
            400: "Ошибка при выполнении запроса.",
            500: "Внутренняя ошибка сервера."
        }
    )
    def get(self, request):
        try:
            project_id = request.GET.get('project_id')
            
            # Фильтрация разделов
            filter_conditions = {}
            if project_id:
                filter_conditions['project_id'] = project_id

            sections = Section.objects.filter(**filter_conditions).select_related('project')

            sections_data = []
            for section in sections:
                # Получаем родительские задачи (где parenttask_id равен id)
                parent_tasks = Task.objects.filter(
                    section=section,
                    parenttask_id=models.F('id')
                ).select_related('user')

                cards = []
                for task in parent_tasks:
                    # Получаем подзадачи для этой задачи (исключая саму родительскую задачу)
                    subtasks = Task.objects.filter(
                        parenttask_id=task.id
                    ).exclude(  # Добавляем exclude чтобы исключить родительскую задачу
                        id=task.id
                    ).values(
                        'id', 'text', 'priority', 'description', 
                        'user_id', 'isdone', 'deadline'
                    )
                    
                    card = {
                        'id': task.id,
                        'title': task.text,
                        'isdone':task.isdone,
                        'priority': task.priority,
                        'description': task.description,
                        'user_id': task.user.id if task.user else None,
                        'section_id':task.section_id,
                        'parenttask_id': task.parenttask_id,
                        'subtasks': list(subtasks),  # Преобразуем QuerySet в список
                        'deadline':task.deadline
                    }
                    cards.append(card)

                section_data = {
                    'id': section.id,
                    'title': section.name,
                    'cards': cards,
                    'project_id': section.project.id,
                }
                sections_data.append(section_data)

            return Response(
                {"data": sections_data, "message": "Разделы и задачи успешно получены."},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {"error": str(e), "message": "Ошибка при получении данных."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class SectionCreateView(APIView):
    @swagger_auto_schema(
        operation_description="Добавление нового раздела",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['section_name', 'project_id'],
            properties={
                'section_name': openapi.Schema(type=openapi.TYPE_STRING, description='Название раздела'),
                'project_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='ID проекта'),
            },
        ),
        responses={
            201: openapi.Response(
                description="Раздел успешно создан",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'data': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'name': openapi.Schema(type=openapi.TYPE_STRING),
                                'project_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                            }
                        ),
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                    }
                )
            ),
            400: "Неверные входные данные",
            500: "Внутренняя ошибка сервера"
        }
    )
    def post(self, request):
        try:
            section_name = request.data.get('section_name')
            project_id = request.data.get('project_id')
            
            if not section_name or not project_id:
                return Response(
                    {"error": "Необходимо указать section_name и project_id", "message": "Ошибка валидации."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Создаем раздел через ORM (id будет автоматически сгенерирован)
            section = Section.objects.create(
                name=section_name,
                project_id=project_id
            )
            
            # Формируем ответ с созданным разделом
            created_section = {
                'id': section.id,  # автоинкрементное поле
                'name': section.name,
                'project_id': section.project_id,
            }
            
            return Response(
                {
                    "data": created_section,
                    "message": "Раздел успешно создан."
                },
                status=status.HTTP_201_CREATED
            )
            
        except Exception as e:
            return Response(
                {"error": str(e), "message": "Ошибка при создании раздела."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
class TaskCreateView(APIView):
    @swagger_auto_schema(
        operation_description="Добавление новой задачи",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['text', 'section_id'],
            properties={
                'text': openapi.Schema(type=openapi.TYPE_STRING, description='Текст задачи'),
                'section_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='ID раздела'),
                'description': openapi.Schema(type=openapi.TYPE_STRING, description='Описание задачи', default=None),
                'deadline': openapi.Schema(type=openapi.TYPE_STRING, format='date-time', description='Срок выполнения', default=None),
                'priority': openapi.Schema(type=openapi.TYPE_INTEGER, description='Приоритет задачи', default=0),
                'user_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='ID пользователя', default=None),
                'isdone': openapi.Schema(type=openapi.TYPE_BOOLEAN, description='Статус выполнения задачи', default=False),
                'dateofcreation': openapi.Schema(type=openapi.TYPE_STRING, format='date-time', description='Дата создания задачи', default=None),
            },
        ),
        responses={
            201: openapi.Response(
                description="Задача успешно создана",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'data': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                                'text': openapi.Schema(type=openapi.TYPE_STRING),
                                'section_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                                'isdone': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                                'dateofcreation': openapi.Schema(type=openapi.TYPE_STRING, format='date-time'),
                                'parenttask_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                            }
                        ),
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                    }
                )
            ),
            400: "Неверные входные данные",
            500: "Внутренняя ошибка сервера"
        }
    )
    def post(self, request):
        try:
            text = request.data.get('text')
            section_id = request.data.get('section_id')
            
            if not text or not section_id:
                return Response(
                    {"error": "Необходимо указать text и section_id", "message": "Ошибка валидации."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            task_data = {
                'text': text,
                'section_id': section_id,
                'description': request.data.get('description'),
                'deadline': request.data.get('deadline'),
                'priority': request.data.get('priority', 0),
                'user_id': request.data.get('user_id'),
                'isdone': request.data.get('isdone', False),
                'dateofcreation': request.data.get('dateofcreation') or timezone.now().isoformat(),
            }
            
            with connection.cursor() as cursor:
                # Создаем задачу и сразу устанавливаем parenttask_id = id
                sql = """
                    INSERT INTO crm_task (
                        text, section_id, description, deadline, priority, 
                        user_id, isdone, dateofcreation, parenttask_id
                    ) VALUES (
                        %(text)s, %(section_id)s, %(description)s, %(deadline)s, 
                        %(priority)s, %(user_id)s, %(isdone)s, %(dateofcreation)s,
                        (SELECT currval(pg_get_serial_sequence('crm_task','id')))
                    )
                    RETURNING id, text, section_id, isdone, dateofcreation, parenttask_id
                """
                cursor.execute(sql, task_data)
                row = cursor.fetchone()
                
                created_task = {
                    'id': row[0],
                    'text': row[1],
                    'section_id': row[2],
                    'isdone': row[3],
                    'dateofcreation': row[4],
                    'parenttask_id': row[5],
                }
            
            return Response(
                {
                    "success": True,
                    "data": created_task,
                    "message": "Задача успешно создана."
                },
                status=status.HTTP_201_CREATED
            )
        
        except Exception as e:
            return Response(
                {
                    "success": False,
                    "error": str(e),
                    "message": "Ошибка при создании задачи."
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class SubtaskCreateView(APIView):
    @swagger_auto_schema(
        operation_description="Добавление новой подзадачи",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['text', 'section_id', 'parenttask_id', 'user_id'],
            properties={
                'text': openapi.Schema(type=openapi.TYPE_STRING, description='Текст подзадачи'),
                'section_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='ID раздела'),
                'parenttask_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='ID родительской задачи'),
                'description': openapi.Schema(type=openapi.TYPE_STRING, description='Описание подзадачи', default=""),
                'deadline': openapi.Schema(type=openapi.TYPE_STRING, format='date-time', description='Срок выполнения', default=None),
                'priority': openapi.Schema(type=openapi.TYPE_INTEGER, description='Приоритет подзадачи', default=0),
                'user_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='ID пользователя'),
                'isdone': openapi.Schema(type=openapi.TYPE_BOOLEAN, description='Статус выполнения подзадачи', default=False),
            },
        ),
        responses={
            201: openapi.Response(
                description="Подзадача успешно создана",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'data': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                                'text': openapi.Schema(type=openapi.TYPE_STRING),
                                'section_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                                'isdone': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                                'dateofcreation': openapi.Schema(type=openapi.TYPE_STRING, format='date-time'),
                                'parenttask_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                                'user_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                            }
                        ),
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                    }
                )
            ),
            400: "Неверные входные данные",
            404: "Родительская задача не найдена",
            500: "Внутренняя ошибка сервера"
        }
    )
    def post(self, request):
        try:
            required_fields = ['text', 'section_id', 'parenttask_id', 'user_id']
            if not all(request.data.get(field) for field in required_fields):
                return Response(
                    {"error": f"Необходимо указать: {', '.join(required_fields)}", 
                     "message": "Ошибка валидации."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Проверяем существование родительской задачи
            parent_task = Task.objects.filter(id=request.data['parenttask_id']).first()
            if not parent_task:
                return Response(
                    {"error": "Родительская задача не найдена", "message": "Ошибка валидации."},
                    status=status.HTTP_404_NOT_FOUND
                )

            deadline_str = request.data.get('deadline')
            deadline_date = None

            if deadline_str:
                try:
                    deadline_date = datetime.strptime(deadline_str, '%Y-%m-%d').date()
                except ValueError:
                    return Response(
                        {"error": "Неверный формат даты. Используйте YYYY-MM-DD"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            task_data = {
                'text': request.data['text'],
                'section_id': request.data['section_id'],
                'parenttask_id': request.data['parenttask_id'],
                'user_id': request.data['user_id'],
                'description': request.data.get('description', ""),
                'deadline': deadline_date or timezone.now().date(),  # Используем date вместо datetime
                'priority': request.data.get('priority', 0),
                'isdone': request.data.get('isdone', False),
                'dateofcreation': timezone.now().date()  # Используем date вместо datetime
            }

            # Создаем подзадачу с помощью ORM
            task = Task.objects.create(**task_data)

            created_task = {
                'id': task.id,
                'text': task.text,
                'section_id': task.section_id,
                'isdone': task.isdone,
                'dateofcreation': task.dateofcreation.isoformat(),
                'parenttask_id': task.parenttask_id,
                'user_id': task.user_id,
            }

            return Response(
                {
                    "success": True,
                    "data": created_task,
                    "message": "Подзадача успешно создана."
                },
                status=status.HTTP_201_CREATED
            )

        except Exception as e:
            return Response(
                {
                    "success": False,
                    "error": str(e),
                    "message": "Ошибка при создании подзадачи."
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
# views.py
from rest_framework.permissions import IsAuthenticated

from drf_yasg.utils import swagger_auto_schema
from django.shortcuts import get_object_or_404
from django.db import transaction


class DeleteTaskView(APIView):
    @transaction.atomic
    def delete(self, request, task_id):
        try:
            task = get_object_or_404(Task, id=task_id)
            task.delete()  # Каскадное удаление сработает автоматически
            
            return Response(
                {"success": True},
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            return Response(
                {
                    "success": False,
                    "error": str(e),
                    "message": "Ошибка при удалении задачи"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DeleteSectionView(APIView):
    @transaction.atomic
    def delete(self, request, section_id):
        try:
            section = get_object_or_404(Section, id=section_id)
            section.delete()  # Каскадное удаление сработает автоматически
            
            return Response(
                {"success": True, "message": "Раздел и его задачи удалены"},
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            return Response(
                {
                    "success": False,
                    "error": str(e),
                    "message": "Ошибка при удалении раздела"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class ToggleTaskStatusView(APIView):
    @transaction.atomic
    def post(self, request, task_id):
        try:
            task = get_object_or_404(Task, id=task_id)
            task.isdone = not task.isdone  # Инвертируем текущее значение
            task.save()
            
            return Response(
                {
                    "success": True,
                    "new_status": task.isdone,
                    "message": f"Статус задачи успешно изменён на {'выполнена' if task.isdone else 'не выполнена'}"
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            return Response(
                {
                    "success": False,
                    "error": str(e),
                    "message": "Ошибка при изменении статуса задачи"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
class UpdateTaskView(APIView):
    @transaction.atomic
    def post(self, request, task_id):
        try:
            task = get_object_or_404(Task, id=task_id)
            
            # Обновляем поля задачи из данных запроса
            fields_to_update = {
                'text': 'text',
                'description': 'description',
                'is_completed': 'isdone',
                'deadline': 'deadline',
                'priority': 'priority',
                'section': 'section_id',
                'parenttask': 'parenttask_id',
                'assignee_id': 'user_id',
                'title': 'text'  # Если title сохраняется в text
            }

            print(request.data)
            print(task.user)
            print(request.data['assignee_id'])
            
            for field, model_field in fields_to_update.items():
                if field in request.data:
                    setattr(task, model_field, request.data[field])
            
            task.save()

            print(task.user)
            
            return Response(
                {
                    "success": True,
                    "message": "Задача успешно обновлена",
                    "task": {
                        "id": task.id,
                        "title": task.text,  # Или другое поле, если title хранится отдельно
                        "text": task.text,
                        "description": task.description,
                        "is_completed": task.isdone,
                        "dateofcreation": task.dateofcreation,
                        "deadline": task.deadline,
                        "priority": task.priority,
                        "section": task.section_id,
                        "parenttask": task.parenttask_id,
                        "user": task.user_id
                    }
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            return Response(
                {
                    "success": False,
                    "error": str(e),
                    "message": "Ошибка при обновлении задачи"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class UpdateSectionView(APIView):
    @transaction.atomic
    def post(self, request, section_id):
        try:
            section = get_object_or_404(Section, id=section_id)
            
            # Проверяем наличие нового названия в запросе
            if 'name' not in request.data or not request.data['name'].strip():
                return Response(
                    {
                        "success": False,
                        "message": "Название раздела не может быть пустым"
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Обновляем название раздела
            new_name = request.data['name'].strip()
            section.name = new_name
            section.save()
            
            return Response(
                {
                    "success": True,
                    "message": "Название раздела успешно изменено",
                    "section": {
                        "id": section.id,
                        "name": section.name,
                        "project": section.project_id
                    }
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            return Response(
                {
                    "success": False,
                    "error": str(e),
                    "message": "Ошибка при изменении названия раздела"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class TaskAssigneeView(APIView):
    def get(self, request, task_id):
        try:
            # Получаем задачу или возвращаем 404 если не найдена
            task = get_object_or_404(Task, id=task_id)
            
            # Получаем исполнителя задачи
            assignee = task.user
            
            # Формируем данные ответа
            response_data = {
                "success": True,
                "task_id": task.id,
                "task_text": task.text,
                "assignee": {
                    'id': assignee.id,
                    'first_name': assignee.first_name,
                    'last_name': assignee.last_name,
                },
                "status": "done" if task.isdone else "in_progress"
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {
                    "success": False,
                    "error": str(e),
                    "message": "Ошибка при получении исполнителя задачи"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )