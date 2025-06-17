from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.contrib.auth import get_user_model
from src.external.lms.models import Grade, Subject

# Создавайте свои представления здесь
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.contrib.auth import get_user_model
from src.external.lms.models import Grade, Subject
from django.utils import timezone
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans


User = get_user_model()

class OptimalTeamFormationView(APIView):
    @swagger_auto_schema(
        operation_description="Формирование оптимальной команды для выбранного предмета и типа задания",
        manual_parameters=[
            openapi.Parameter(
                'subject_id',
                openapi.IN_QUERY,
                description="ID предмета",
                type=openapi.TYPE_INTEGER,
                required=True
            ),
            openapi.Parameter(
                'task_type',
                openapi.IN_QUERY,
                description="Тип задания (programming, design, science, business)",
                type=openapi.TYPE_STRING,
                required=True
            ),
            openapi.Parameter(
                'team_size',
                openapi.IN_QUERY,
                description="Размер команды",
                type=openapi.TYPE_INTEGER,
                required=False,
                default=3
            )
        ],
        responses={
            200: openapi.Response(
                description="Оптимальная команда",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'team': openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            items=openapi.Schema(
                                type=openapi.TYPE_OBJECT,
                                properties={
                                    'user_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                                    'full_name': openapi.Schema(type=openapi.TYPE_STRING),
                                    'grades': openapi.Schema(
                                        type=openapi.TYPE_ARRAY,
                                        items=openapi.Schema(
                                            type=openapi.TYPE_OBJECT,
                                            properties={
                                                'subject': openapi.Schema(type=openapi.TYPE_STRING),
                                                'grade': openapi.Schema(type=openapi.TYPE_NUMBER),
                                            }
                                        )
                                    ),
                                    'average_grade': openapi.Schema(type=openapi.TYPE_NUMBER),
                                    'cluster': openapi.Schema(type=openapi.TYPE_INTEGER),
                                    'relevance_score': openapi.Schema(type=openapi.TYPE_NUMBER)
                                }
                            )
                        ),
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                    }
                )
            ),
            400: "Неверные параметры запроса",
            500: "Внутренняя ошибка сервера"
        }
    )
    def get(self, request):
        try:
            # Получаем параметры запроса
            subject_id = request.query_params.get('subject_id')
            task_type = request.query_params.get('task_type')
            team_size = int(request.query_params.get('team_size', 3))
            
            # Валидация параметров
            if not subject_id or not task_type:
                return Response(
                    {"error": "Необходимо указать subject_id и task_type"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Получаем данные из базы
            subject = Subject.objects.get(pk=subject_id)
            grades = Grade.objects.filter(subject=subject).select_related('student')
            
            # Формируем DataFrame для анализа
            data = []
            for grade in grades:
                user = grade.student
                data.append({
                    'user_id': user.id,
                    'full_name': f"{user.first_name} {user.last_name}",
                    'subject': subject.name,
                    'grade': grade.grade,
                    'date_received': grade.related
                })
            
            if not data:
                return Response(
                    {"error": "Нет данных об успеваемости по выбранному предмету"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Создаем DataFrame
            df = pd.DataFrame(data)
            
            # Группируем по пользователям
            user_grades = df.groupby(['user_id', 'full_name']).agg({
                'grade': list,
                'subject': lambda x: list(x.unique())
            }).reset_index()
            
            # Добавляем среднюю оценку
            user_grades['average_grade'] = user_grades['grade'].apply(np.mean)
            
            # Определяем типы задач
            task_types = {
                'programming': ['алгоритмы', 'программирование', 'структуры данных'],
                'design': ['дизайн', 'графика', 'рисование'],
                'science': ['физика', 'химия', 'математика'],
                'business': ['экономика', 'менеджмент', 'маркетинг']
            }
            
            if task_type not in task_types:
                return Response(
                    {"error": f"Неизвестный тип задачи. Доступные: {list(task_types.keys())}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Кластеризация пользователей
            features = user_grades[['average_grade']]
            scaler = StandardScaler()
            scaled_features = scaler.fit_transform(features)
            
            # Определяем оптимальное число кластеров
            best_score = -1
            best_k = 2
            max_clusters = min(10, len(user_grades) - 1)
            
            for k in range(2, max_clusters + 1):
                kmeans = KMeans(n_clusters=k, random_state=42)
                labels = kmeans.fit_predict(scaled_features)
                score = silhouette_score(scaled_features, labels)
                if score > best_score:
                    best_score = score
                    best_k = k
            
            # Выполняем кластеризацию
            kmeans = KMeans(n_clusters=best_k, random_state=42)
            user_grades['cluster'] = kmeans.fit_predict(scaled_features)
            
            # Формируем команду
            target_skills = task_types[task_type]
            
            # Рассчитываем релевантность (в данном случае просто используем среднюю оценку)
            user_grades['relevance_score'] = user_grades['average_grade']
            
            # Сортируем по релевантности и выбираем лучших
            team = user_grades.sort_values('relevance_score', ascending=False).head(team_size)
            
            # Формируем ответ
            team_data = []
            for _, row in team.iterrows():
                grades_list = []
                for subj, grade in zip(row['subject'], row['grade']):
                    grades_list.append({
                        'subject': subj,
                        'grade': grade
                    })
                
                team_data.append({
                    'user_id': row['user_id'],
                    'full_name': row['full_name'],
                    'grades': grades_list,
                    'average_grade': row['average_grade'],
                    'cluster': row['cluster'],
                    'relevance_score': row['relevance_score']
                })
            
            return Response({
                "team": team_data,
                "message": f"Сформирована команда из {len(team_data)} участников"
            }, status=status.HTTP_200_OK)
            
        except Subject.DoesNotExist:
            return Response(
                {"error": "Предмет не найден"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": str(e), "message": "Ошибка при формировании команды"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
class AllUsersAcademicPerformanceView(APIView):
    @swagger_auto_schema(
        operation_description="Получение информации обо всех пользователях, пройденных предметах и оценках",
        responses={
            200: openapi.Response(
                description="Данные о всех пользователях и их успеваемости",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'users': openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            items=openapi.Schema(
                                type=openapi.TYPE_OBJECT,
                                properties={
                                    'user_info': openapi.Schema(
                                        type=openapi.TYPE_OBJECT,
                                        properties={
                                            'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                                            'full_name': openapi.Schema(type=openapi.TYPE_STRING),
                                            
                                        }
                                    ),
                                    'subjects_grades': openapi.Schema(
                                        type=openapi.TYPE_ARRAY,
                                        items=openapi.Schema(
                                            type=openapi.TYPE_OBJECT,
                                            properties={
                                                'subject_name': openapi.Schema(type=openapi.TYPE_STRING),
                                                'grades': openapi.Schema(
                                                    type=openapi.TYPE_ARRAY,
                                                    items=openapi.Schema(
                                                        type=openapi.TYPE_OBJECT,
                                                        properties={
                                                            'grade_value': openapi.Schema(type=openapi.TYPE_INTEGER),
                                                        }
                                                    )
                                                ),
                                                'average_grade': openapi.Schema(type=openapi.TYPE_NUMBER),
                                            }
                                        )
                                    ),
                                }
                            )
                        ),
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                    }
                )
            ),
            500: "Внутренняя ошибка сервера"
        }
    )
    def get(self, request):
        try:
            # Получаем всех пользователей
            users = User.objects.all()
            
            # Получаем все оценки с предварительной выборкой связанных данных
            grades = Grade.objects.all().select_related(
                'student', 
                'subject', 
            )
            
            # Создаем словарь для группировки оценок по пользователям и предметам
            users_data = {}
            
            for grade in grades:
                user_id = grade.student.id
                subject_id = grade.subject.id
                
                # Инициализируем данные пользователя, если их еще нет
                if user_id not in users_data:
                    user = grade.student
                    users_data[user_id] = {
                        'user_info': {
                            'id': user.id,
                            'full_name': f"{user.first_name} {user.last_name}",
                        },
                        'subjects': {}
                    }
                
                # Инициализируем данные предмета, если их еще нет
                if subject_id not in users_data[user_id]['subjects']:
                    subject = grade.subject
                    users_data[user_id]['subjects'][subject_id] = {
                        'subject_name': subject.name,
                        'grades': [],
                        'total_grade': 0,
                        'grades_count': 0
                    }
                
                # Добавляем оценку
                users_data[user_id]['subjects'][subject_id]['grades'].append({
                    'grade_value': grade.grade,
                })
                users_data[user_id]['subjects'][subject_id]['total_grade'] += grade.grade
                users_data[user_id]['subjects'][subject_id]['grades_count'] += 1
            
            # Формируем итоговый результат
            result = []
            for user_id, user_data in users_data.items():
                subjects_list = []
                for subject in user_data['subjects'].values():
                    subject['average_grade'] = round(
                        subject['total_grade'] / subject['grades_count'], 2
                    ) if subject['grades_count'] > 0 else 0
                    del subject['total_grade']
                    del subject['grades_count']
                    subjects_list.append(subject)
                
                result.append({
                    'user_info': user_data['user_info'],
                    'subjects_grades': subjects_list
                })
            
            # Добавляем пользователей без оценок
            users_without_grades = [
                {
                    'user_info': {
                        'id': user.id,
                        'full_name': f"{user.first_name} {user.last_name}",
                    },
                    'subjects_grades': []
                }
                for user in users if user.id not in users_data
            ]
            result.extend(users_without_grades)
            
            return Response(
                {
                    "users": result,
                    "message": f"Получены данные для {len(result)} пользователей."
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            return Response(
                {"error": str(e), "message": "Ошибка при получении данных об успеваемости."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )