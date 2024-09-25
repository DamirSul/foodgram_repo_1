from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']

    email = models.EmailField(
        verbose_name='Адрес электронной почты',
        max_length=128,
        unique=True,
        help_text=(
            f'Адрес электронной почты, не более 128 символов'
        ),
    )
    username = models.CharField(
        verbose_name='Имя пользователя',
        max_length=64,
        unique=True,
    )
    first_name = models.CharField(
        verbose_name='Имя Отчество',
        max_length=128,
        blank=True,
        null=True,
        help_text=(
            f'Имя Отчество, не более 128 символов'
        ),
    )
    last_name = models.CharField(
        verbose_name='Фамилия',
        max_length=128,
        blank=True,
        null=True,
        help_text=(
            f'Фамилия, не более 128 символов'
        ),
    )
    is_subscribed = models.BooleanField(
        default=False,
        verbose_name='Подписка'
    )
    avatar = models.URLField(
        verbose_name='Аватар',
        max_length=200,
        blank=True,
        null=True
    )

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self):
        return self.username