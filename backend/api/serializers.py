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
    avatar = Base64ImageField(required=False, read_only=True)

    class Meta:
        model = User
        fields = ['email', 'id', 'username', 'first_name', 'last_name', 'is_subscribed', 'avatar']

    def get_is_subscribed(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return Subscription.objects.filter(user=request.user, author=obj).exists()
        return False


class IngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = ['id', 'name', 'measurement_unit']


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['id', 'name', 'slug']


class RecipeIngredientSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source='ingredient.id')

    class Meta:
        model = RecipeIngredient
        fields = ['id', 'amount']


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
        #print(instance.ingredients)
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
        representation['ingredients'] = [
            {
                'id': ingredient.ingredient.id,
                'name': ingredient.ingredient.name,
                'measurement_unit': ingredient.ingredient.measurement_unit,
                'amount': ingredient.amount,
            }
            for ingredient in instance.recipe_ingredients.all()
        ]
        return representation

    def create(self, validated_data):
        ingredients_data = validated_data.pop('recipe_ingredients')
        tags_data = validated_data.pop('tags', [])
        recipe = Recipe.objects.create(**validated_data)

        for ingredient_data in ingredients_data:
            ingredient_id = ingredient_data['ingredient']['id']
            ingredient_amount = ingredient_data['amount']
            RecipeIngredient.objects.create(recipe=recipe, ingredient_id=ingredient_id, amount=ingredient_amount)

        # Устанавливаем теги
        recipe.tags.set(tags_data)
        return recipe
    
    def update(self, instance, validated_data):
        # Обновляем основные поля рецепта
        instance.name = validated_data.get('name', instance.name)
        instance.text = validated_data.get('text', instance.text)
        instance.cooking_time = validated_data.get('cooking_time', instance.cooking_time)
        instance.image = validated_data.get('image', instance.image)
        instance.save()

        # Обновляем ингредиенты
        ingredients_data = validated_data.pop('recipe_ingredients', [])
        if ingredients_data:
            # Удаляем старые ингредиенты
            RecipeIngredient.objects.filter(recipe=instance).delete()
            # Добавляем новые ингредиенты
            for ingredient_data in ingredients_data:
                ingredient_id = ingredient_data['ingredient']['id']
                ingredient_amount = ingredient_data['amount']
                RecipeIngredient.objects.create(
                    recipe=instance,
                    ingredient_id=ingredient_id,
                    amount=ingredient_amount
                )

        # Обновляем теги
        tags_data = validated_data.pop('tags')
        if tags_data:
            instance.tags.set(tags_data)

        return instance


  
class SubscriptionSerializer(serializers.ModelSerializer):
    recipes = RecipeSerializer(many=True)
    user = serializers.StringRelatedField()

    class Meta:
        model = Subscription
        fields = ['user', 'recipes', 'recipe_count']

class FavoriteSerializer(serializers.ModelSerializer):
    recipe = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Favorite
        fields = ['id', 'recipe']

class ShoppingCartSerializer(serializers.ModelSerializer):
    recipe = serializers.PrimaryKeyRelatedField(queryset=Recipe.objects.all())

    class Meta:
        model = ShoppingCart
        fields = ('recipe',)

    def validate(self, data):
        user = self.context['request'].user
        recipe = data['recipe']

        # Проверка на существование рецепта в списке покупок
        if ShoppingCart.objects.filter(user=user, recipe=recipe).exists():
            raise serializers.ValidationError('Этот рецепт уже есть в списке покупок.')

        return data

    def create(self, validated_data):
        user = self.context['request'].user
        recipe = validated_data['recipe']

        # Создание новой записи в списке покупок
        shopping_cart = ShoppingCart.objects.create(user=user, recipe=recipe)
        return shopping_cart

