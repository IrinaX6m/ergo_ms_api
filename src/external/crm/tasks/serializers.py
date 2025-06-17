from rest_framework import serializers
from src.external.crm.models import Section, Task

# Создавайте свои сериализаторы здесь

class SectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Section
        fields = ['id', 'name', 'project']
        extra_kwargs = {'project': {'required': True}}

class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = ['id', 'text', 'description', 'isdone', 'priority', 'section', 'user']
        extra_kwargs = {
            'section': {'required': True},
            'user': {'required': True}
        }