import base64

from rest_framework import serializers, status
from django.core.files.base import ContentFile
from rest_framework.exceptions import PermissionDenied
from food.models import Ingredient, Tag, Recipe, Subscription, Favorite, ShoppingCart, RecipeIngredient, RecipeTag
from users.models import User
from rest_framework.response import Response

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
    tags = serializers.PrimaryKeyRelatedField(many=True, queryset=Tag.objects.all(), write_only=True)
    image = Base64ImageField(required=True)  # Поле image обязательно
    author = serializers.ReadOnlyField(source='author.username')
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()

    class Meta:
        model = Recipe
        fields = ['id', 'name', 'text', 'cooking_time', 'ingredients', 'tags', 'image', 'is_favorited', 'is_in_shopping_cart', 'author']

    def to_representation(self, instance):
        request = self.context.get('request')
        
        # Проверяем, что это запрос на избранное
        if request and 'favorite' in request.path:
            # Возвращаем только необходимые данные для запроса на добавление в избранное
            return {
                'id': instance.id,
                'name': instance.name,
                'image': request.build_absolute_uri(instance.image.url) if instance.image else None,
                'cooking_time': instance.cooking_time,
            }

        # Для остальных запросов возвращаем полное представление
        representation = super().to_representation(instance)
        representation['tags'] = TagSerializer(instance.tags.all(), many=True).data
        representation['author'] = {
            'id': instance.author.id,
            'username': instance.author.username,
            'first_name': instance.author.first_name,
            'last_name': instance.author.last_name,
            'email': instance.author.email,
            'is_subscribed': instance.author.is_subscribed,
            'avatar': instance.author.avatar.url if instance.author.avatar else None,
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


    def validate_ingredients(self, ingredients):
        if not ingredients:
            raise serializers.ValidationError("Поле ingredients не может быть пустым.")
        
        ingredient_ids = []
        for ingredient_data in ingredients:
            if ingredient_data['amount'] < 1:
                raise serializers.ValidationError("Количество ингредиента должно быть больше 0.")
            if ingredient_data['ingredient']['id'] in ingredient_ids:
                raise serializers.ValidationError("Ингредиенты не должны повторяться.")
            ingredient_ids.append(ingredient_data['ingredient']['id'])

            # Проверка существования ингредиента
            try:
                Ingredient.objects.get(id=ingredient_data['ingredient']['id'])
            except Ingredient.DoesNotExist:
                raise serializers.ValidationError(f"Ингредиент с ID {ingredient_data['ingredient']['id']} не найден.")
        
        return ingredients

    def validate_tags(self, tags):
        if not tags:
            raise serializers.ValidationError("Поле tags не может быть пустым.")
        if len(tags) != len(set(tags)):
            raise serializers.ValidationError("Теги не должны повторяться.")
        return tags

    def validate_cooking_time(self, cooking_time):
        if cooking_time < 1:
            raise serializers.ValidationError("Время готовки должно быть больше 0.")
        return cooking_time

    def create(self, validated_data):
        ingredients_data = validated_data.pop('recipe_ingredients')
        tags_data = validated_data.pop('tags', [])
        recipe = Recipe.objects.create(**validated_data)

        for ingredient_data in ingredients_data:
            ingredient_id = ingredient_data['ingredient']['id']
            ingredient_amount = ingredient_data['amount']
            ingredient_instance = Ingredient.objects.get(id=ingredient_id)
            RecipeIngredient.objects.create(recipe=recipe, ingredient=ingredient_instance, amount=ingredient_amount)

        recipe.tags.set(tags_data)
        return recipe

    def update(self, instance, validated_data):
        ingredients_data = validated_data.pop('recipe_ingredients', [])
        tags_data = validated_data.pop('tags', [])

        if not ingredients_data:
            raise serializers.ValidationError("Поле ingredients не может быть пустым.")
        if not tags_data:
            raise serializers.ValidationError("Поле tags не может быть пустым.")

        instance.name = validated_data.get('name', instance.name)
        instance.text = validated_data.get('text', instance.text)
        instance.cooking_time = validated_data.get('cooking_time', instance.cooking_time)
        instance.image = validated_data.get('image', instance.image)
        instance.save()

        if ingredients_data:
            RecipeIngredient.objects.filter(recipe=instance).delete()
            for ingredient_data in ingredients_data:
                ingredient_id = ingredient_data['ingredient']['id']
                ingredient_amount = ingredient_data['amount']
                RecipeIngredient.objects.create(
                    recipe=instance,
                    ingredient_id=ingredient_id,
                    amount=ingredient_amount
                )

        if tags_data:
            instance.tags.set(tags_data)

        return instance

    def get_is_favorited(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return Favorite.objects.filter(author=request.user, recipe=obj).exists()
        return False

    def get_is_in_shopping_cart(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return ShoppingCart.objects.filter(author=request.user, recipe=obj).exists()
        return False


    def validate(self, data):
        request = self.context.get('request')
        if request.method in ['PUT', 'PATCH'] and request.user != self.instance.author:
            raise PermissionDenied("Вы не можете редактировать чужой рецепт.")  # Используем PermissionDenied
        return data


class UserSerializer(serializers.ModelSerializer):
    avatar = serializers.SerializerMethodField()
    is_subscribed = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['email', 'id', 'username', 'first_name', 'last_name', 'is_subscribed', 'avatar']

    def get_is_subscribed(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return Subscription.objects.filter(user=request.user, author=obj).exists()
        return False

    def get_avatar(self, obj):
        request = self.context.get('request')
        if obj.avatar and hasattr(obj.avatar, 'url'):
            return request.build_absolute_uri(obj.avatar.url)
        return None

    def to_representation(self, instance):
        representation = super().to_representation(instance)

        # Проверяем, что это запрос на подписки
        request = self.context.get('request')


        if request and ('subscriptions' in request.path or 'subscribe' in request.path):
            # Добавляем рецепты и их количество только для подписок
            recipes = Recipe.objects.filter(author=instance)
            recipes_limit = request.query_params.get('recipes_limit', None)
            if recipes_limit is not None:
                try:
                    recipes_limit = int(recipes_limit)
                    recipes = recipes[:recipes_limit]  # Ограничиваем количество рецептов
                except ValueError:
                    # Если не удалось преобразовать в int, используем все рецепты
                    pass
            representation['recipes'] = [
                {
                    'id': recipe.id,
                    'name': recipe.name,
                    'image': request.build_absolute_uri(recipe.image.url) if recipe.image else None,
                    'cooking_time': recipe.cooking_time,
                }
                for recipe in recipes
            ]
            representation['recipes_count'] = recipes.count()

        return representation





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

class ShoppingCartSerializer(serializers.ModelSerializer):
    recipe = RecipeSerializer()

    class Meta:
        model = ShoppingCart
        fields = ('recipe',)




