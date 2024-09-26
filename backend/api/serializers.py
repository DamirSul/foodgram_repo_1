import base64

from rest_framework import serializers
from django.core.files.base import ContentFile

from food.models import Ingredient, Tag, Recipe, Subscription, Favorite, ShoppingCart, RecipeIngredient, RecipeTag
from users.models import User


class Base64ImageField(serializers.ImageField):
    def to_internal_value(self, data):
        # Если данные пустые, возвращаем пустое значение
        if not data:
            return super().to_internal_value(data)

        # Если данные в формате Base64, декодируем их
        if isinstance(data, str):
            # Проверяем, содержит ли строка метаданные
            if data.startswith('data:image'):
                format, imgstr = data.split(';base64,')
                ext = format.split('/')[-1]
                # Создаем временный файл
                data = ContentFile(base64.b64decode(imgstr), name=f'temp.{ext}')

        return super().to_internal_value(data)


class UserSerializer(serializers.ModelSerializer):
    is_subscribed = serializers.SerializerMethodField()
    avatar = serializers.ImageField(source='profile.avatar', read_only=True)

    class Meta:
        model = User
        fields = ['email', 'id', 'username', 'first_name', 'last_name', 'is_subscribed', 'avatar']

    def get_is_subscribed(self, obj):
        return False  # Здесь можно реализовать логику проверки подписки


class IngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = ['id', 'name', 'measurement_unit']

class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['id', 'name', 'slug']


class RecipeIngredientSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source='ingredient.id')  # Извлекаем ID ингредиента

    class Meta:
        model = RecipeIngredient
        fields = ['id', 'amount']  # Оставляем только id и amount


class RecipeSerializer(serializers.ModelSerializer):
    ingredients = RecipeIngredientSerializer(many=True, source='recipe_ingredients')
    tags = serializers.PrimaryKeyRelatedField(many=True, queryset=Tag.objects.all(), write_only=True)  # Поле для записи тегов
    image = Base64ImageField(required=False, allow_null=True)
    author = serializers.ReadOnlyField(source='author.username')

    class Meta:
        model = Recipe
        fields = ['id', 'name', 'text', 'cooking_time', 'ingredients', 'tags', 'image', 'is_favorited', 'is_in_shopping_cart', 'author']

    def to_representation(self, instance):
        representation = super().to_representation(instance)

        # Получаем информацию о тегах
        representation['tags'] = TagSerializer(instance.tags.all(), many=True).data  # Используем TagSerializer
        #representation['author'] = UserSerializer(instance.author, read_only=True).data
        representation['author'] = {
            'id': instance.author.id,
            'username': instance.author.username,
            'first_name': instance.author.first_name,
            'last_name': instance.author.last_name,
            'email': instance.author.email,
            'is_subscribed': instance.author.is_subscribed,
            'avatar': instance.author.avatar.url if instance.author.avatar else None,  # Проверяем наличие аватара
        }

        return representation

    def create(self, validated_data):
        ingredients_data = validated_data.pop('recipe_ingredients')
        tags_data = validated_data.pop('tags', [])  # Извлекаем теги

        recipe = Recipe.objects.create(**validated_data)

        for ingredient_data in ingredients_data:
            ingredient_id = ingredient_data['ingredient']['id']
            ingredient_amount = ingredient_data['amount']
            RecipeIngredient.objects.create(recipe=recipe, ingredient_id=ingredient_id, amount=ingredient_amount)

        # Устанавливаем теги
        recipe.tags.set(tags_data)
        return recipe





class SubscriptionSerializer(serializers.ModelSerializer):
    recipes = RecipeSerializer(many=True)
    user = serializers.StringRelatedField()

    class Meta:
        model = Subscription
        fields = ['user', 'recipes', 'recipe_count']

class FavoriteSerializer(serializers.ModelSerializer):
    recipe = RecipeSerializer()

    class Meta:
        model = Favorite
        fields = ['author', 'recipe']

class ShoppingCartSerializer(serializers.ModelSerializer):
    recipe = RecipeSerializer()

    class Meta:
        model = ShoppingCart
        fields = ['author', 'recipe', 'cooking_time']
