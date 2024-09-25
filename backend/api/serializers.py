import base64

from rest_framework import serializers
from django.core.files.base import ContentFile

from food.models import Ingredient, Tag, Recipe, Subscription, Favorite, ShoppingCart, RecipeIngredient
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


# class RecipeIngredientSerializer(serializers.ModelSerializer):
#     id = serializers.IntegerField(source='ingredient.id')  # Используйте source для извлечения ID из ингредиента
#     amount = serializers.IntegerField()  # Убедитесь, что поле amount также присутствует

#     class Meta:
#         model = RecipeIngredient
#         fields = ['id', 'amount']  # Используйте 'id' вместо 'ingredient'

class RecipeIngredientSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField()  # source='ingredient.id'
    amount = serializers.IntegerField()

    class Meta:
        model = RecipeIngredient
        fields = ['id', 'amount']


class RecipeSerializer(serializers.ModelSerializer):
    ingredients = RecipeIngredientSerializer(many=True)
    tags = serializers.PrimaryKeyRelatedField(many=True, queryset=Tag.objects.all())
    image = Base64ImageField(required=False, allow_null=True)

    class Meta:
        model = Recipe
        fields = ['name', 'text', 'cooking_time', 'ingredients', 'tags', 'image']


    def create(self, validated_data):
        print("Полученные данные для создания рецепта:", validated_data)  # Отладочный вывод

        ingredients_data = validated_data.pop('ingredients')
        tags_data = validated_data.pop('tags')

        print("Ингредиенты:", ingredients_data)  # Отладочный вывод
        print("Теги:", tags_data)  # Отладочный вывод

        recipe = Recipe.objects.create(**validated_data)
        print("Созданный рецепт:", recipe.pk)  # Отладочный вывод

        for ingredient_data in ingredients_data:
            print("Текущий ингредиент:", ingredient_data)  # Отладочный вывод
            try:
                ingredient_id = ingredient_data['id']
                print(f'ИДшник ингредиента {ingredient_id}')
                ingredient_amount = ingredient_data['amount']
                RecipeIngredient.objects.create(recipe=recipe, ingredient_id=ingredient_id, amount=ingredient_amount)
                print(f"Ингредиент {ingredient_id} добавлен в рецепт с количеством {ingredient_amount}.")  # Отладочный вывод
            except KeyError as e:
                print(f"Ошибка KeyError: {e}. Проверьте, правильно ли передаются данные.")  # Отладочный вывод

        recipe.tags.set(tags_data)
        print("Теги успешно установлены для рецепта.")  # Отладочный вывод

        return recipe



# class RecipeIngredientSerializer(serializers.ModelSerializer):
#     id = serializers.PrimaryKeyRelatedField(queryset=Ingredient.objects.all(), source='ingredient.id')
#     amount = serializers.IntegerField()

#     class Meta:
#         model = RecipeIngredient
#         fields = ['id', 'amount']


# class RecipeSerializer(serializers.ModelSerializer):
#     ingredients = RecipeIngredientSerializer(many=True)
#     image = Base64ImageField(required=False, allow_null=True)
#     tags = serializers.PrimaryKeyRelatedField(queryset=Tag.objects.all(), many=True)

#     class Meta:
#         model = Recipe
#         fields = ['id', 'ingredients', 'tags', 'image', 'name', 'text', 'cooking_time']

#     def create(self, validated_data):
#         ingredients_data = validated_data.pop('ingredients')
#         tags_data = validated_data.pop('tags')
#         image_data = validated_data.pop('image', None)

#         print("validated_data:", validated_data)
#         print("ingredients_data:", ingredients_data)

#         # Создание рецепта
#         recipe = Recipe.objects.create(image=image_data, **validated_data)

#         # Добавление ингредиентов
#         for ingredient_data in ingredients_data:
#             # Извлекаем id из вложенного словаря
#             ingredient_instance = ingredient_data['ingredient']['id']  
#             RecipeIngredient.objects.create(
#                 recipe=recipe,
#                 ingredient=ingredient_instance,
#                 amount=ingredient_data['amount']
#             )

#         # Добавление тегов
#         recipe.tags.set(tags_data)

#         return recipe


    # def to_representation(self, instance):
    #     """ Переопределяем вывод данных для рецепта """
    #     representation = super().to_representation(instance)
    #     ingredients = RecipeIngredient.objects.filter(recipe=instance)
        
    #     # Формируем данные для ингредиентов вручную
    #     representation['ingredients'] = [
    #         {
    #             'id': ingredient.ingredient.id,
    #             'name': ingredient.ingredient.name,  # Можно добавить название для удобства
    #             'amount': ingredient.amount
    #         }
    #         for ingredient in ingredients
    #     ]
    #     return representation

    # def create(self, validated_data):
    #     # Обработка ингредиентов
    #     ingredients_data = validated_data.pop('ingredients')
    #     tags_data = validated_data.pop('tags')
    #     image_data = validated_data.pop('image', None)

    #     print("Полученные данные для создания рецепта:")
    #     print("validated_data:", validated_data)
    #     print("ingredients_data:", ingredients_data)
    #     print("tags_data:", tags_data)

    #     # Декодирование изображения
    #     image = None
    #     if image_data:
    #         if isinstance(image_data, ContentFile):
    #             image = image_data
    #         else:
    #             format, imgstr = image_data.split(';base64,')
    #             ext = format.split('/')[-1]
    #             image = ContentFile(base64.b64decode(imgstr), name=f'temp.{ext}')
    #             print("Изображение успешно декодировано.")

    #     # Создание рецепта
    #     recipe = Recipe.objects.create(image=image, **validated_data)
    #     print(f"Рецепт {recipe.name} создан с ID {recipe.id}.")

    #     # Добавление ингредиентов
    #     for ingredient_data in ingredients_data:
    #         print("ingredient_data:", ingredient_data)

    #         # Получаем объект ингредиента
    #         ingredient_instance = ingredient_data['id']
    #         amount = ingredient_data['amount']

    #         print(f"Используем ингредиент: {ingredient_instance.name}")
    #         print(f"Количество ингредиента: {amount}")

    #         # Добавление ингредиента в рецепт
    #         RecipeIngredient.objects.create(
    #             recipe=recipe,
    #             ingredient=ingredient_instance,
    #             amount=amount
    #         )
    #         print(f"Ингредиент {ingredient_instance.name} добавлен в рецепт.")

    #     # Добавление тегов
    #     recipe.tags.set(tags_data)

    #     print(f"Рецепт {recipe.name} успешно создан с ID {recipe.id}.")
    #     return recipe





    
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
