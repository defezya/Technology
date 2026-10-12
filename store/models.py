from django.conf import settings
from django.db import models
from django.utils import timezone

class Category(models.Model):
    name = models.CharField("Название", max_length=100, unique=True)
    slug = models.SlugField("Адрес", max_length=110, unique=True)
    def __str__(self):
        return self.name
    class Meta:
        verbose_name = "категория"
        verbose_name_plural = "Категории"

class Product(models.Model):
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products", verbose_name="Категория")
    name = models.CharField("Название товара", max_length=200)
    description = models.TextField("Описание", blank=True)
    manufacturer = models.CharField("Производитель", max_length=120, blank=True)
    year = models.PositiveSmallIntegerField("Год выпуска", null=True, blank=True)
    model_name = models.CharField("Модель", max_length=120, blank=True)
    price = models.DecimalField("Цена, ₽", max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField("В наличии", default=0)
    image = models.ImageField("Фото", upload_to="products/", blank=True, null=True)
    created_at = models.DateTimeField("Добавлен", default=timezone.now)
    active = models.BooleanField("Показывать в каталоге", default=True)
    def __str__(self):
        return self.name
    class Meta:
        ordering = ["-created_at"]
        verbose_name = "товар"
        verbose_name_plural = "Товары"

class Order(models.Model):
    STATUS_CHOICES = [
        ("new", "Новый"),
        ("confirmed", "Подтверждён"),
        ("cancelled", "Отменён"),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="orders", verbose_name="Покупатель")
    created_at = models.DateTimeField("Дата заказа", default=timezone.now)
    status = models.CharField("Статус", max_length=20, choices=STATUS_CHOICES, default="new")
    total = models.DecimalField("Сумма", max_digits=12, decimal_places=2, default=0)
    def __str__(self):
        return f"Заказ №{self.pk} — {self.user}"
    class Meta:
        ordering = ["-created_at"]
        verbose_name = "заказ"
        verbose_name_plural = "Заказы"

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items", verbose_name="Заказ")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, verbose_name="Товар")
    quantity = models.PositiveIntegerField("Количество")
    price = models.DecimalField("Цена на момент заказа", max_digits=10, decimal_places=2)
    def __str__(self):
        return f"{self.product} × {self.quantity}"
    class Meta:
        verbose_name = "позиция заказа"
        verbose_name_plural = "Позиции заказов"
