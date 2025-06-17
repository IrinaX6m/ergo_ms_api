from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from django.contrib.auth import authenticate
from django.utils.crypto import get_random_string

from src.core.utils.methods import (
    parse_errors_to_dict, 
    send_confirmation_email,
)
from src.core.cms.adp.models import EmailConfirmationCode
from src.core.cms.adp.serializers import (
    UserLoginSerializer, 
    UserRegistrationSerializer,
    UserRegistrationValidationSerializer,
)
from src.core.utils.base.base_views import BaseAPIView

from django.contrib.auth.models import User

from src.core.utils.database.main import OrderedDictQueryExecutor

class UserRegistrationValidationView(BaseAPIView):
    @swagger_auto_schema(
        operation_description="Регистрация нового пользователя.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,

            properties={
                'first_name': openapi.Schema(
                    type=openapi.TYPE_STRING, 
                    description='Имя'
                ),
                'username': openapi.Schema(
                    type=openapi.TYPE_STRING, 
                    description='Логин'
                ),
                'email': openapi.Schema(
                    type=openapi.TYPE_STRING, 
                    format=openapi.FORMAT_EMAIL, 
                    description='Электронная почта'
                ),
                'password': openapi.Schema(
                    type=openapi.TYPE_STRING, 
                    format=openapi.FORMAT_PASSWORD, 
                    description='Пароль'
                ),
                'password_confirm': openapi.Schema(
                    type=openapi.TYPE_STRING, 
                    format=openapi.FORMAT_PASSWORD, 
                    description='Подтверждение пароля'
                ),
                'is_superuser': openapi.Schema(
                    type=openapi.TYPE_BOOLEAN,                      
                    description='Является ли суперпользователем'
                ),
            },

            required=['first_name', 'username', 'email', 'password', 'password_confirm'],
        ),
        responses={
            201: "Пользователь успешно зарегистрирован.",
            400: "Регистрация не успешна."
        },
    )
    def post(self, request):
        serializer = UserRegistrationValidationSerializer(data=request.data)
        
        #Command.handle('createsuperuser',username='myusername', email='myemail@example.com', password='mypassword')
        
        if serializer.is_valid():
            #User.objects.create_user(username=serializer.field_name, email= serializer.email, password= serializer.password, is_superuser=True).save()
            successful_response = Response(
                {"message": "Валидация успешна."}, 
                status=status.HTTP_200_OK
            )
            return successful_response
        
        errors = parse_errors_to_dict(serializer.errors)
        return Response(
            errors, 
            status=status.HTTP_400_BAD_REQUEST
        )

class SendConfirmationCodeView(BaseAPIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Отправка кода подтверждения.",
    )   
    def post(self, request):
        email = request.data.get("email")
        if not email:
            return Response({"error": "Отсутствует Email"}, status=status.HTTP_400_BAD_REQUEST)

        # Генерация 6-значного кода
        code = get_random_string(length=6, allowed_chars='0123456789')
        
        # Обновляем или создаём запись для email
        _ = EmailConfirmationCode.objects.update_or_create(
            email=email,
            defaults={"code": code},
        )
        
        # Отправляем email
        send_confirmation_email(email, code)

        return Response({"message": "Код подтверждения отправлен"}, status=status.HTTP_200_OK)

class VerifyConfirmationCodeView(BaseAPIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Проверка кода подтверждения.",
    )
    def post(self, request):
        email = request.data.get("email")
        code = request.data.get("code")


        if not email or not code:
            return Response({"error": "Email и код обязательны"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            confirmation_code = EmailConfirmationCode.objects.get(email=email)
        except EmailConfirmationCode.DoesNotExist:
            return Response({"error": "Неверный Email или код"}, status=status.HTTP_400_BAD_REQUEST)

        if confirmation_code.code == code:
            # Код верен, можно выполнить дальнейшие действия
            # Удаляем запись после успешной проверки
            confirmation_code.delete()
            return Response({"message": "Код успешно подтвержден"}, status=status.HTTP_200_OK)
        else:
            return Response({"error": "Неверный код"}, status=status.HTTP_400_BAD_REQUEST)
        
class UserRegistrationView(BaseAPIView):
    @swagger_auto_schema(
        operation_description="Проверка регистрации.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,

            properties={
                'first_name': openapi.Schema(
                    type=openapi.TYPE_STRING, 
                    description='Имя'
                ),
                'username': openapi.Schema(
                    type=openapi.TYPE_STRING, 
                    description='Логин'
                ),
                'email': openapi.Schema(
                    type=openapi.TYPE_STRING, 
                    format=openapi.FORMAT_EMAIL, 
                    description='Электронная почта'
                ),
                'password': openapi.Schema(
                    type=openapi.TYPE_STRING, 
                    format=openapi.FORMAT_PASSWORD, 
                    description='Пароль'
                ),
                'password_confirm': openapi.Schema(
                    type=openapi.TYPE_STRING, 
                    format=openapi.FORMAT_PASSWORD, 
                    description='Подтверждение пароля'
                ),
                'is_superuser': openapi.Schema(
                    type=openapi.TYPE_BOOLEAN,                      
                    description='Является ли суперпользователем'
                ),
            },

            required=['first_name', 'username', 'email', 'password', 'password_confirm'],
        ),
        responses={
            201: "Пользователь успешно зарегистрирован.",
            400: "Регистрация не успешна."
        },
    )
    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)

        if serializer.is_valid():
            User.objects.create_superuser(username=serializer.validated_data['username'], email= serializer.validated_data['email'], password= serializer.validated_data['password']).save()

            successful_response = Response(
                {"message": "Регистрация успешна."}, 
                status=status.HTTP_200_OK
            )
            return successful_response

        errors = parse_errors_to_dict(serializer.errors)
        return Response(
            errors, 
            status=status.HTTP_400_BAD_REQUEST
        )

class UserAuthorizationView(BaseAPIView):
    @swagger_auto_schema(
        operation_description="Авторизация пользователя.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'username': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Логин'
                ),
                'password': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format=openapi.FORMAT_PASSWORD,
                    description='Пароль'
                ),
                'password_confirm': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format=openapi.FORMAT_PASSWORD,
                    description='Подтверждение пароля'
                ),
            },
            required=['username', 'password', 'password_confirm'],
        ),
        responses={
            200: openapi.Response(
                description="Пользователь успешно авторизован.",
                examples={
                    "application/json": {
                        "refresh": "your_refresh_token",
                        "access": "your_access_token",
                        "user_id": 1  # Добавьте это в пример ответа
                    }
                }
            ),
            400: "Авторизация не успешна."
        },
    )
    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)

        if serializer.is_valid():
            username = serializer.validated_data['username']
            password = serializer.validated_data['password']

            user = authenticate(request, username=username, password=password)

            if user is not None:
                refresh = RefreshToken.for_user(user)
                return Response(
                    {
                        'refresh': str(refresh),
                        'access': str(refresh.access_token),
                        'user_id': user.id  # Добавьте ID пользователя в ответ
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "message": "Неверные учетные данные."
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        errors = parse_errors_to_dict(serializer.errors)
        return Response(
            errors,
            status=status.HTTP_400_BAD_REQUEST
        )

class ProtectedView(BaseAPIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Защищенное представление.",
        responses={
            200: "Вы авторизованы.",
            401: "Неавторизованный доступ."
        },
        security=[{'Bearer': []}]
    )
    def get(self, request):
        return Response(
            {"message": "Вы авторизованы."}, 
            status=status.HTTP_200_OK
        )