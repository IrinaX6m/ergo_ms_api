from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from src.external.crm.models import Task, Project, User, Section, Calendar  # ✅ Добавлены Project и User
from django.utils import timezone  # ✅ Импортируем timezone
from rest_framework.permissions import IsAuthenticated
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.core.exceptions import ObjectDoesNotExist  # ✅ Импортируем исключение
from src.external.crm.calendar.serializers import CalendarTaskSerializer  
from django.db import connection
from src.external.crm.calendar.serializers import ProjectSerializer, SectionSerializer



class CalendarTaskListView(APIView):
    """
    Возвращает список задач для календаря
    """
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Получение всех задач с deadline",
        responses={
            200: openapi.Response("Список задач", openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=openapi.Schema(type=openapi.TYPE_OBJECT, properties={
                    'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'text': openapi.Schema(type=openapi.TYPE_STRING),
                    'deadline': openapi.Schema(type=openapi.TYPE_STRING, format='date-time'),
                    'priority': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'user': openapi.Schema(type=openapi.TYPE_STRING, description='Имя пользователя'),
                })
            )),
            500: "Ошибка сервера"
        }
    )
    def get(self, request):
        try:
            # Получаем все задачи с deadline
            tasks = Task.objects.filter(deadline__isnull=False).select_related('user')

            task_list = []
            for task in tasks:
                task_data = {
                    'id': task.id,
                    'text': task.text,
                    'deadline': task.deadline.isoformat() if task.deadline else None,
                    'priority': task.priority,
                    'user': task.user.username if task.user else 'Не назначен'
                }
                task_list.append(task_data)

            return Response(task_list, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    def post(self, request):
        serializer = CalendarTaskSerializer(data=request.data)
        if serializer.is_valid():
            try:
                project = Project.objects.get(id=serializer.validated_data['project'])
                user = User.objects.get(id=serializer.validated_data['user'])

                Task.objects.create(
                    text=serializer.validated_data['text'],
                    deadline=serializer.validated_data['deadline'],
                    priority=serializer.validated_data['priority'],
                    description=serializer.validated_data.get('description', ''),
                    project=project,
                    user=user,
                    dateofcreation=timezone.now(),
                    
                )
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            except (ObjectDoesNotExist, Exception) as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
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
class ProjectListView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Получение списка проектов пользователя",
        responses={
            200: openapi.Response("Список проектов", ProjectSerializer(many=True)),
            500: "Ошибка сервера"
        }
    )
    def get(self, request):
        try:
            user_id = request.query_params.get('user_id') or request.user.id
            if not user_id:
                return Response(
                    {"error": "User ID is required"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            projects = Project.objects.filter(creator_id=user_id)
            serializer = ProjectSerializer(projects, many=True)
            return Response(serializer.data)
        
        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class SectionsByProjectView(APIView):
    """
    Получение разделов по ID проекта
    """
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Получение разделов по ID проекта",
        manual_parameters=[
            openapi.Parameter('project_id', openapi.IN_PATH, description="ID проекта", type=openapi.TYPE_INTEGER)
        ],
        responses={
            200: openapi.Response("Список разделов", openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=openapi.Schema(type=openapi.TYPE_OBJECT, properties={
                    'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'name': openapi.Schema(type=openapi.TYPE_STRING),
                })
            )),
            404: "Проект не найден",
            500: "Ошибка сервера"
        }
    )
    def get(self, request, project_id):
        try:
            project = Project.objects.get(id=project_id)
            sections = Section.objects.filter(project=project)
            serializer = SectionSerializer(sections, many=True)
            return Response(serializer.data)
        except Project.DoesNotExist:
            return Response(
                {"error": f"Project with id {project_id} not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
from django.shortcuts import get_object_or_404
from django.db import transaction
class DeleteTaskView(APIView):
    @swagger_auto_schema(
        operation_description="Удаление задачи по ID",
        responses={
            200: openapi.Response("Задача успешно удалена"),
            404: "Задача не найдена",
            500: "Внутренняя ошибка"
        }
    )
    def delete(self, request, task_id):
        try:
            # Удаляем задачу
            task = Task.objects.get(id=task_id)
            task.delete()

            return Response(
                {"success": True, "message": "Задача удалена"},
                status=status.HTTP_200_OK
            )

        except Task.DoesNotExist:
            return Response(
                {"success": False, "error": "Задача не найдена"},
                status=status.HTTP_404_NOT_FOUND
            )

        except Exception as e:
            return Response(
                {"success": False, "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
from .models import Holidays
from .serializers import HolidaysSerializer

class HolidaysAPIView(APIView):
    def get(self, request):
        holidays = Holidays.objects.all()
        serializer = HolidaysSerializer(holidays, many=True)
        return Response(serializer.data)