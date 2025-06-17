from django.db import models
from django.contrib.auth.models import User

from src.external.settings.models import Category, Tag

class CmsShortcodeCategory(models.Model):
    name = models.CharField(max_length=100)

class CmsShortcodeTemplate(models.Model):
    name = models.CharField(max_length=100, unique=True)
    component_type = models.ForeignKey(
        'CmsShortcodeCategory',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='templates'
    )
    class_list = models.JSONField(default=list, blank=True)
    extra_data = models.JSONField(default=dict, blank=True)  # Например: {"text": "Купить", "icon": "cart"}
    is_active = models.BooleanField(default=True)
    icon_name = models.CharField(max_length=100, blank=True, null=True, help_text='Имя иконки из lucide-vue-next')
    allow_children = models.BooleanField(default=False, help_text='Можно ли вкладывать в этот компонент другие компоненты')
    creator = models.ForeignKey(User, on_delete=models.CASCADE)
    date_of_creation = models.DateField(auto_now_add=True)
    last_update = models.DateTimeField(auto_now=True)
    position = models.PositiveIntegerField(default=0)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='children')
    content = models.TextField(blank=True, help_text='Опциональный HTML или текст')

    def __str__(self):
        return f"{self.name} ({self.component_type})"
    
class CmsPage(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug  = models.SlugField(max_length=100, unique=True,
                            blank=True, null=True)         
    creator = models.ForeignKey(User, on_delete=models.CASCADE)
    date_of_creation = models.DateTimeField(auto_now_add=True)
    last_update = models.DateTimeField(auto_now=True)
    
    # Добавляем категорию
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pages',
        verbose_name="Категория страницы"
    )
    category_index = models.BooleanField(
        default=False,
        help_text='Если True — страница открывается по URL самой категории'
    )

    # Добавляем теги
    tags = models.ManyToManyField(
        Tag,
        blank=True,
        related_name="pages",
        verbose_name="Теги страницы"
    )

    is_homepage = models.BooleanField(
        default=False,
        verbose_name="Главная страница",
        help_text="Является ли эта страница главной"
    )
    def get_full_url(self):
        """
        /electronics/           ← страница-индекс категории «electronics»
        /electronics/tv-samsung ← обычная страница с slug-ом
        """
        parts = []
        cat = self.category
        while cat:
            parts.insert(0, cat.slug)
            cat = cat.parent

        if not self.category_index:
            parts.append(self.slug)

        return '/' + '/'.join(parts)
    
    full_url = property(get_full_url)

    @classmethod
    def get_homepage(cls):
        return cls.objects.filter(is_homepage=True).first()
    
    def save(self, *args, **kwargs):
        if self.is_homepage:
            CmsPage.objects.filter(is_homepage=True).exclude(pk=self.pk).update(is_homepage=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
    
    class Meta:
        # страница-индекс должна быть уникальна в рамках категории
        constraints = [
            models.UniqueConstraint(
                fields=['category'],
                condition=models.Q(category_index=True),
                name='unique_category_index'
            )
        ]
    
class CmsShortcodeInstance(models.Model):
    page = models.ForeignKey(CmsPage, on_delete=models.CASCADE, related_name='instances', db_index=True)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='children', db_index=True)
    template = models.ForeignKey(CmsShortcodeTemplate, on_delete=models.PROTECT, help_text='Шаблон компонента')
    class_list = models.JSONField(default=list, blank=True)
    extra_data = models.JSONField(default=dict, blank=True)
    position = models.PositiveIntegerField(default=0)
    date_of_creation = models.DateTimeField(auto_now_add=True)
    last_update = models.DateTimeField(auto_now=True)
    uid = models.CharField(max_length=64, unique=True, db_index=True)
    is_active = models.BooleanField(default=True)
    icon_name = models.CharField(max_length=100, blank=True, null=True)
    allow_children = models.BooleanField(default=False)

    class Meta:
        # При получении моделей, сортировка будет происходить по значению position
        ordering = ['position']
        # Уникальность позиции в пределах одного родителя
        constraints = [
            models.UniqueConstraint(fields=['parent', 'position'], name='unique_position_per_parent')
        ]

    def __str__(self):
        return f"{self.template.name} on {self.page.slug if self.page else 'внутри другого блока'}"

class SiteLayout(models.Model):
    """Синглтон: какие шаблоны брать для шапки и подвала по умолчанию"""
    header_template = models.ForeignKey(
        CmsShortcodeTemplate,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='+'
    )
    footer_template = models.ForeignKey(
        CmsShortcodeTemplate,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='+'
    )
    menu_pages = models.ManyToManyField(
        CmsPage,
        blank=True,
        related_name='+'
    )

    def save(self, *args, **kwargs):
        """гарантируем единственную запись"""
        self.pk = 1
        super().save(*args, **kwargs)

    def __str__(self):
        return 'Site-wide layout (singleton)'

    class Meta:
        verbose_name = 'Глобальный Layout'
        verbose_name_plural = 'Глобальный Layout'