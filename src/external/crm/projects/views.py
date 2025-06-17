from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from src.external.crm.models import Project, User_Project,Task
from django.db.models import Count
from django.contrib.auth import get_user_model
from django.utils import timezone
import logging
from django.db import transaction
from django.shortcuts import get_object_or_404

User = get_user_model()
logger = logging.getLogger(__name__)


class UserAllProjectsView(APIView):
    @swagger_auto_schema(
        operation_description="Получение всех проектов пользователя",
        manual_parameters=[
            openapi.Parameter(
                'user_id',
                openapi.IN_QUERY,
                description="ID пользователя",
                type=openapi.TYPE_INTEGER,
                required=True
            )
        ],
        responses={
            200: openapi.Response(
                description="Список проектов пользователя",
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
                                    'dateofcreation': openapi.Schema(type=openapi.TYPE_STRING, format='date'),
                                    'creator_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                                    'user_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                                    'deadline': openapi.Schema(type=openapi.TYPE_STRING, format='date'),
                                    'description': openapi.Schema(type=openapi.TYPE_STRING)
                                }
                            )
                        ),
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                    }
                )
            ),
            400: "Не указан ID пользователя",
            404: "Пользователь не найден",
            500: "Внутренняя ошибка сервера"
        }
    )
    def get(self, request):
        try:
            user_id = request.query_params.get('user_id')
            if not user_id:
                return Response(
                    {"error": "Необходимо указать user_id", "message": "Ошибка валидации."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            try:
                user = User.objects.get(pk=user_id)
            except User.DoesNotExist:
                return Response(
                    {"error": "Пользователь не найден", "message": "Ошибка валидации."},
                    status=status.HTTP_404_NOT_FOUND
                )
            user_projects = User_Project.objects.filter(user_id=user_id).select_related('project')
            projects_data = [{
                'id': user_project.project.id,
                'name': user_project.project.name,
                'dateofcreation': user_project.project.dateofcreation,
                'creator_id': user_project.project.creator_id,
                'user_id': user_project.user_id,
                'deadline': user_project.project.deadline,
                'description': user_project.project.description,
            } for user_project in user_projects]
            return Response(
                {
                    "data": projects_data,
                    "message": f"Найдено {len(projects_data)} проектов."
                },
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {"error": str(e), "message": "Ошибка при получении проектов."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ProjectCreateView(APIView):
    def post(self, request):
        try:
            # Валидация данных
            name = request.data.get('name', '').strip()
            description = request.data.get('description', '').strip()
            deadline_str = request.data.get('deadline', '').strip()
            if not name:
                return Response(
                    {"message": "Название проекта обязательно"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            # Проверка на авторизацию
            if not request.user.is_authenticated:
                return Response(
                    {"message": "Требуется авторизация"},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            # Парсинг даты дедлайна
            deadline = timezone.now().date()  # Значение по умолчанию
            if deadline_str:
                try:
                    deadline = timezone.datetime.strptime(deadline_str, '%Y-%m-%d').date()
                except ValueError:
                    return Response(
                        {"message": "Неверный формат даты. Используйте YYYY-MM-DD"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            # Создание проекта
            project = Project.objects.create(
                name=name,
                description=description,
                deadline=deadline,
                creator=request.user,
            )
            # Автоматически добавляем создателя в проект
            user_project = User_Project.objects.create(
                project=project,
                user=request.user,
                isnew=True
            )
            # Формирование успешного ответа
            return Response(
                {
                    "id": project.id,
                    "name": project.name,
                    "description": project.description,
                    "creator_id": project.creator.id,
                    "dateofcreation": project.dateofcreation.strftime('%Y-%m-%d'),
                    "deadline": project.deadline.strftime('%Y-%m-%d'),
                },
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            logger.error(f"Ошибка при создании проекта: {str(e)}", exc_info=True)
            return Response(
                {
                    "message": "Внутренняя ошибка сервера",
                    "details": str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class DeletePersonalProjectView(APIView):
    @transaction.atomic
    def delete(self, request, project_id): 
        print("dada")
        try:
            print(id)
            project = get_object_or_404(Project, id=project_id)  
            project.delete()
            
            return Response(
                {"success": True, "message": "Проект и его задачи удалены"},
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            return Response(
                {
                    "success": False,
                    "error": str(e),
                    "message": "Ошибка при удалении проекта"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
class LeaveProjectView(APIView):
    @transaction.atomic
    def delete(self, request, user_id,project_id): 
        print("dada")
        try:
            print(id)
            user_project = get_object_or_404(User_Project, user_id=user_id,project_id=project_id)  
            user_project.delete()
            
            return Response(
                {"success": True, "message": "Вы вышли из проекта"},
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            return Response(
                {
                    "success": False,
                    "error": str(e),
                    "message": "Ошибка при выходе из проекта"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class PersonalProjectsView(APIView):
    @swagger_auto_schema(
        operation_description="Получение личных проектов пользователя (где он создатель)",
        manual_parameters=[
            openapi.Parameter(
                'user_id',
                openapi.IN_QUERY,
                description="ID пользователя",
                type=openapi.TYPE_INTEGER,
                required=True
            )
        ],
        responses={
            200: openapi.Response(
                description="Список личных проектов пользователя",
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
                                    'dateofcreation': openapi.Schema(type=openapi.TYPE_STRING, format='date'),
                                    'creator_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                                    'deadline': openapi.Schema(type=openapi.TYPE_STRING, format='date'),
                                    'description': openapi.Schema(type=openapi.TYPE_STRING)
                                }
                            )
                        ),
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                    }
                )
            ),
            400: "Не указан ID пользователя",
            404: "Пользователь не найден",
            500: "Внутренняя ошибка сервера"
        }
    )
    def get(self, request):
        try:
            user_id = request.query_params.get('user_id')
            if not user_id:
                return Response(
                    {"error": "Необходимо указать user_id", "message": "Ошибка валидации."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            try:
                user = User.objects.get(pk=user_id)
            except User.DoesNotExist:
                return Response(
                    {"error": "Пользователь не найден", "message": "Ошибка валидации."},
                    status=status.HTTP_404_NOT_FOUND
                )
            # Получаем проекты, где пользователь является создателем (через модель Project)
            projects = Project.objects.filter(creator_id=user_id)
            projects_data = [{
                'id': project.id,
                'name': project.name,
                'dateofcreation': project.dateofcreation,
                'creator_id': project.creator_id,
                'deadline': project.deadline,
                'description': project.description,
            } for project in projects]
            return Response(
                {
                    "data": projects_data,
                    "message": f"Найдено {len(projects_data)} проектов."
                },
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {"error": str(e), "message": "Ошибка при получении проектов."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class InvitedProjectsView(APIView):
    @swagger_auto_schema(
        operation_description="Получение проектов, куда пользователь приглашен (где он участник, но не создатель)",
        manual_parameters=[
            openapi.Parameter(
                'user_id',
                openapi.IN_QUERY,
                description="ID пользователя",
                type=openapi.TYPE_INTEGER,
                required=True
            )
        ],
        responses={
            200: openapi.Response(
                description="Список приглашенных проектов пользователя",
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
                                    'dateofcreation': openapi.Schema(type=openapi.TYPE_STRING, format='date'),
                                    'creator_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                                    'deadline': openapi.Schema(type=openapi.TYPE_STRING, format='date'),
                                    'description': openapi.Schema(type=openapi.TYPE_STRING)
                                }
                            )
                        ),
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                    }
                )
            ),
            400: "Не указан ID пользователя",
            404: "Пользователь не найден",
            500: "Внутренняя ошибка сервера"
        }
    )
    def get(self, request):
        try:
            user_id = request.query_params.get('user_id')
            if not user_id:
                return Response(
                    {"error": "Необходимо указать user_id", "message": "Ошибка валидации."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            try:
                user = User.objects.get(pk=user_id)
            except User.DoesNotExist:
                return Response(
                    {"error": "Пользователь не найден", "message": "Ошибка валидации."},
                    status=status.HTTP_404_NOT_FOUND
                )
            # Получаем ID проектов, где пользователь является создателем
            owned_project_ids = Project.objects.filter(creator_id=user_id).values_list('id', flat=True)
            # Получаем проекты, где пользователь участник, но не создатель
            invited_projects = User_Project.objects.filter(
                user_id=user_id
            ).exclude(
                project_id__in=owned_project_ids
            ).select_related('project')
            projects_data = [{
                'id': up.project.id,
                'name': up.project.name,
                'dateofcreation': up.project.dateofcreation,
                'creator_id': up.project.creator_id,
                'deadline': up.project.deadline,
                'description': up.project.description,
            } for up in invited_projects]
            return Response(
                {
                    "data": projects_data,
                    "message": f"Найдено {len(projects_data)} проектов, где вы являетесь участником."
                },
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {"error": str(e), "message": "Ошибка при получении списка проектов."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
class ProjectTasksCountView(APIView):
    @swagger_auto_schema(
        operation_description="Получение количества задач по ID проекта",
        manual_parameters=[
            openapi.Parameter(
                'project_id', openapi.IN_QUERY, 
                description="ID проекта", 
                type=openapi.TYPE_INTEGER, 
                required=True
            ),
            openapi.Parameter(
                'count_done', openapi.IN_QUERY, 
                description="Учитывать только выполненные задачи (true/false)", 
                type=openapi.TYPE_BOOLEAN,
                required=False
            )
        ],
        responses={
            200: openapi.Response(
                description="Количество задач в проекте",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'tasks_count': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'done_count': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'active_count': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                    }
                )
            ),
            400: "Неверный запрос",
            404: "Проект не найден",
            500: "Внутренняя ошибка сервера"
        }
    )
    def get(self, request):
        try:
            project_id = request.query_params.get('project_id')
            count_done = request.query_params.get('count_done')

            if not project_id:
                return Response(
                    {"error": "project_id обязателен", "message": "Укажите ID проекта в параметрах запроса."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                project = Project.objects.get(id=project_id)
            except Project.DoesNotExist:
                return Response(
                    {"error": "Проект не найден", "message": f"Проект с ID {project_id} не существует."},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Получаем все задачи проекта через секции
            tasks = Task.objects.filter(section__project=project)
            
            # Общее количество задач
            total_count = tasks.count()
            
            # Количество выполненных задач
            done_count = tasks.filter(isdone=True).count()
            
            # Количество активных задач
            active_count = total_count - done_count

            response_data = {
                "tasks_count": total_count,
                "done_count": done_count,
                "active_count": active_count,
                "message": f"Проект '{project.name}' содержит {total_count} задач."
            }

            # Если запрошен подсчет только выполненных задач
            if count_done == 'true':
                response_data.update({
                    "tasks_count": done_count,
                    "message": f"Проект '{project.name}' содержит {done_count} выполненных задач."
                })
            elif count_done == 'false':
                response_data.update({
                    "tasks_count": active_count,
                    "message": f"Проект '{project.name}' содержит {active_count} активных задач."
                })

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": str(e), "message": "Ошибка при получении данных."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class UpdateProjectView(APIView):
    @transaction.atomic
    def post(self, request, project_id):
        try:
            project = get_object_or_404(Project, id=project_id)
            
            # Обновляем поля проекта из данных запроса
            fields_to_update = {
                'name': 'name',
                'deadline': 'deadline',
                'description': 'description',
                'creator': 'creator_id'  # Если нужно изменить создателя
            }
            
            for field, model_field in fields_to_update.items():
                if field in request.data:
                    # Особое поле для обработки ForeignKey
                    if field == 'creator':
                        creator_id = request.data[field]
                        creator = get_object_or_404(User, id=creator_id)
                        setattr(project, model_field, creator)
                    else:
                        setattr(project, model_field, request.data[field])
            
            project.save()
            
            return Response(
                {
                    "success": True,
                    "message": "Проект успешно обновлен",
                    "project": {
                        "id": project.id,
                        "name": project.name,
                        "dateofcreation": project.dateofcreation,
                        "creator": project.creator_id,
                        "deadline": project.deadline,
                        "description": project.description
                    }
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            return Response(
                {
                    "success": False,
                    "error": str(e),
                    "message": "Ошибка при обновлении проекта"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class ProjectUsersView(APIView):
    def get(self, request, project_id):
        try:
            # Получаем проект или возвращаем 404 если не найден
            project = get_object_or_404(Project, id=project_id)
            
            # Получаем все связи User_Project для данного проекта
            user_projects = User_Project.objects.filter(project=project)
            
            # Собираем данные пользователей
            users_data = []
            for user_project in user_projects:
                user = user_project.user
                users_data.append({
                    'id': user.id,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'is_new': user_project.isnew  # Добавляем статус isnew из связи
                })
            
            return Response(
                {
                    "success": True,
                    "project_id": project.id,
                    "project_name": project.name,
                    "users": users_data
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            return Response(
                {
                    "success": False,
                    "error": str(e),
                    "message": "Ошибка при получении пользователей проекта"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )