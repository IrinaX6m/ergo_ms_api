# crm/calendar/serializers.py

from rest_framework import serializers
from src.external.crm.models import Task, User,Project,Section


class CalendarTaskSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    project = serializers.SerializerMethodField()
    section = serializers.PrimaryKeyRelatedField(queryset=Section.objects.all())

    class Meta:
        model = Task
        fields = [
            'id', 'text', 'deadline', 'priority', 'description',
            'project', 'section', 'user', 'dateofcreation','is_calendar_event'
                
        ]

        extra_kwargs = {
            'deadline': {'required': True},
            'dateofcreation': {'required': True},
            'project': {'required': True},
            'section': {'required': True},
            'user': {'required': True},
        }
class SectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Section
        fields = ['id', 'name', 'project']
class ProjectSerializer(serializers.ModelSerializer):
    sections = SectionSerializer(many=True, read_only=True)

    class Meta:
        model = Project
        fields = ['id', 'name', 'dateofcreation', 'creator', 'deadline', 'description', 'sections']

from .models import Holidays

class HolidaysSerializer(serializers.ModelSerializer):
    class Meta:
        model = Holidays
        fields = ['id', 'date', 'name']    