from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class Project(models.Model):
    name = models.CharField(max_length=100, default='')
    dateofcreation = models.DateField(default=timezone.now)
    creator = models.ForeignKey(User, on_delete= models.CASCADE)
    deadline = models.DateField(default=timezone.now)
    description = models.TextField(default='')

class User_Project(models.Model):
    project = models.ForeignKey(Project, on_delete= models.CASCADE)
    user = models.ForeignKey(User, on_delete= models.CASCADE)
    isnew = models.BooleanField(default=True)

class Section(models.Model):
    name = models.CharField(max_length=100, default='')
    project = models.ForeignKey(Project, on_delete= models.CASCADE)

class Task(models.Model):
    text = models.TextField(default="")
    isdone = models.BooleanField(default=False)
    description = models.TextField(default="")
    dateofcreation = models.DateField(default= timezone.now)
    deadline = models.DateField(default= timezone.now)
    priority = models.IntegerField(default=0)
    section = models.ForeignKey(Section, on_delete=models.CASCADE)
    parenttask = models.ForeignKey('self', on_delete= models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='crm_tasks')

class Calendar (models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField(default='')
    time = models.DateTimeField(default= timezone.now)