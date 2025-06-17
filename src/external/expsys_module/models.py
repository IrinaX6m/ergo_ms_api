from django.db import models
from django.contrib.auth.models import User
from django.contrib.auth.models import AbstractUser
from src.external.lms.models import Subject
import datetime

class Competence(models.Model):
    name = models.CharField(max_length=255, default='')
    description = models.TextField(default='')
    category = models.TextField(default='')

class Indicator(models.Model):
    name = models.CharField(max_length=255, default='')
    description = models.TextField(default='')
    category = models.TextField(default='')


class Indicator_Subject(models.Model):
    indicator = models.ForeignKey(Indicator, on_delete=models.CASCADE,default=0)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, default=0)
    sat_coef = models.FloatField(default=0)
    knowledge = models.TextField(default='')
    ability = models.TextField(default='')
    mastered = models.TextField(default='')

class Indicator_Competence(models.Model):
    indicator = models.ForeignKey(Indicator, on_delete=models.CASCADE,default=0)
    competence = models.ForeignKey(Competence, on_delete=models.CASCADE, default=0)

class Skill(models.Model):
    name =models.CharField(max_length=255, default='')

class Vacance (models.Model):
    name = models.CharField(max_length=255, default='')
    salary_from = models.FloatField(default=0)
    salary_to = models.FloatField(default=0)
    currency = models.CharField(max_length=255, default='')
    area = models.CharField(max_length=255, default='')
    type = models.CharField(max_length=255, default='')
    employment = models.CharField(max_length=255, default='')
    experience = models.CharField(max_length=255, default='')
    skill = models.ManyToManyField(Skill, related_name='vacance_skill')
    

class Skill_Course(models.Model):
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, default=0)
    sat_coef = models.FloatField(default=0)

