from django.db import models

class Holidays(models.Model):
    
    date = models.DateField(default='2000-01-01')  
    name = models.CharField(max_length=255, default='')  
class Meta:
        db_table = 'holidays'
        verbose_name = 'Праздник'
        verbose_name_plural = 'Праздники'

def __str__(self):
        return f"{self.date} - {self.name}"