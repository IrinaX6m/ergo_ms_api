from django.apps import AppConfig

class ExpsysModuleConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'src.external.expsys_module'
    label = 'expsys_module'