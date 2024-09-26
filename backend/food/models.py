from django.db import models

from backend.settings import AUTH_USER_MODEL
from users.models import User


class Ingredient(models.Model):
    name = models.CharField(
        max_length=64,
        verbose_name='Название'
    )
    measurement_unit = models.CharField(
        verbose_name='Единица измерения',
        max_length=16
    )

    class Meta:
        verbose_name = 'Ингредиент'
        verbose_name_plural = 'Ингредиенты'

    def __str__(self):
        return self.name


class Tag(models.Model):
    name = models.CharField(
        verbose_name='Название',
        max_length=64,
        unique=True
    )
    slug = models.SlugField(
        verbose_name='Идентификатор',
        max_length=64,
        unique=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['name', 'slug'],
                name='unique_tag'
            )
        ]

        verbose_name = 'Тег'
        verbose_name_plural = 'Теги'

    def __str__(self):
        return self.name


class Recipe(models.Model):
    author = models.ForeignKey(
        AUTH_USER_MODEL,
        related_name='recipes',
        on_delete=models.CASCADE
    )
    name = models.CharField(
        verbose_name='Название',
        max_length=256
    )
    text = models.TextField(verbose_name='Описание')
    cooking_time = models.PositiveSmallIntegerField(
        verbose_name='Время приготовления'
    )
    image = models.ImageField(verbose_name='Фотография', upload_to='recipes/')
    ingredients = models.ManyToManyField(
        Ingredient,
        through='RecipeIngredient',
        verbose_name='Список ингредиентов',
        related_name='recipes'
    )
    tags = models.ManyToManyField(
        Tag,
        verbose_name='Теги'
    )
    is_favorited = models.BooleanField(
        default=False,
        verbose_name='В списке избранного'
    )
    is_in_shopping_cart = models.BooleanField(
        default=False,
        verbose_name='В списке покупок'
    )

    class Meta:
        verbose_name = 'Рецепт'
        verbose_name_plural = 'Рецепты'
    def __str__(self):
        return self.name



class Subscription(models.Model):
    user = models.ForeignKey(
        AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='subscriptions'
    )
    author = models.ForeignKey(
        AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='subscribers'
    )
    recipes = models.ManyToManyField('Recipe', related_name='subscribers', blank=True)
    recipe_count = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('user', 'author')  # Обеспечивает уникальность подписок
        verbose_name = 'Подписка'
        verbose_name_plural = 'Подписки'

    def __str__(self):
        return f"{self.user.username} подписан на {self.author.username}"

    def save(self, *args, **kwargs):
        # Если подписка сохранена, обновляем количество рецептов
        if self.pk is not None:
            self.recipe_count = self.recipes.count()
        super().save(*args, **kwargs)



class Favorite(models.Model):
    author = models.ForeignKey(
        AUTH_USER_MODEL,
        verbose_name='Пользователь',
        on_delete=models.CASCADE,
        related_name='favorites'
    )
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name='favorited_by'
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['author', 'recipe'],
                name='author_recipe'
            )
        ]
        verbose_name = 'Избранное'
        verbose_name_plural = 'Избранное'


class ShoppingCart(models.Model):
    author = models.ForeignKey(
        AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name='Название',
        max_length=124,
        related_name = 'shopping_cart'
    )
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name='in_shopping_cart'
    )
    cooking_time = models.PositiveSmallIntegerField(
        verbose_name='Время приготовления'
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['author', 'recipe'],
                name='unique_recipe_author'
            )
        ]
        verbose_name = 'Список покупок'
        verbose_name_plural = 'Списки покупок'


class RecipeIngredient(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name='recipe_ingredients')
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE)
    amount = models.PositiveIntegerField(verbose_name='Количество')

    class Meta:
        default_related_name = 'recipe_ingredients'
        constraints = [
            models.UniqueConstraint(
                fields=['recipe', 'ingredient'],
                name='unique_recipe_ingredient'
            )
        ]

    def __str__(self):
        return f"{self.ingredient.name} - {self.amount}"


class RecipeTag(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE)
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['recipe', 'tag'],
                name='unique_recipe_tag'
            )
        ]

    def __str__(self):
        return f"{self.recipe.name} - {self.tag.name}"
