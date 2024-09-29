from django.shortcuts import render
from djoser import views as djoser_views
from rest_framework import status
from rest_framework.response import Response

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, AllowAny

from food.models import Ingredient, Tag, Recipe, Subscription, Favorite, ShoppingCart
from users.models import User
from .serializers import IngredientSerializer, TagSerializer, RecipeSerializer, SubscriptionSerializer, FavoriteSerializer, ShoppingCartSerializer, UserSerializer
from rest_framework.decorators import action
from .pagination import RecipePagination
from django.http import HttpResponse
from django.conf import settings
import random
import string
from food.models import ShortLink
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.core.files.base import ContentFile
import base64


class UserViewSet(djoser_views.UserViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

    @action(detail=False, methods=['get'], url_path='me')
    def me(self, request):
        if request.method == 'GET':
            serializer = self.get_serializer(request.user)
            return Response(data=serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['put'], url_path='me/avatar')
    def update_avatar(self, request):
        user = request.user
        if 'avatar' in request.data:
            # Извлекаем Base64 код
            format, imgstr = request.data['avatar'].split(';base64,')  # 'data:image/png;base64,...'
            ext = format.split('/')[-1]  # Получаем расширение (например, 'png')
            
            # Создаем файл аватара
            avatar_file = ContentFile(base64.b64decode(imgstr), name=f'avatar_{user.id}.{ext}')
            
            # Сохраняем файл в поле аватара пользователя
            user.avatar.save(avatar_file.name, avatar_file)
            user.save()

            # Формируем полный URL для ответа
            avatar_url = request.build_absolute_uri(user.avatar.url)
            
            return Response({'avatar': avatar_url}, status=status.HTTP_200_OK)
        
        return Response({'detail': 'No avatar provided.'}, status=status.HTTP_400_BAD_REQUEST)
        

class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    pagination_class = None
    #permission_classes = [IsAuthenticated]

class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.all().order_by('id')
    serializer_class = TagSerializer
    permission_classes = [AllowAny]
    pagination_class = None


def redirect_to_recipe(request, short_code):
    # Получаем ссылку по короткому коду
    short_link = get_object_or_404(ShortLink, short_code=short_code)
    
    # Получаем полную ссылку на рецепт
    recipe_url = reverse('recipes-detail', kwargs={'pk': short_link.recipe.id})
    
    # Перенаправляем пользователя на полную версию
    return redirect(recipe_url)

class RecipeViewSet(viewsets.ModelViewSet):
    serializer_class = RecipeSerializer
    #permission_classes = [AllowAny]
    pagination_class = RecipePagination
    #permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def get_queryset(self):
        # Устанавливаем порядок, например, по имени
        return Recipe.objects.all().order_by('name')  # Замените 'name' на поле, по которому хотите сортировать



    # Action для добавления в избранное
    @action(detail=True, methods=['post', 'delete'], url_path='favorite')
    def add__to_favorite(self, request, pk=None):
        recipe = self.get_object()
        user = request.user
        
        # Проверяем, что рецепт уже в избранном
        if Favorite.objects.filter(author=user, recipe=recipe).exists():
            Favorite.objects.filter(author=user, recipe=recipe).delete()
            return Response({"Успешно удалено."}, status=status.HTTP_200_OK)
        
        # Добавляем в избранное
        Favorite.objects.create(author=user, recipe=recipe)
        return Response({"Рецепт добавлен в избранное."}, status=status.HTTP_201_CREATED)
    
        # Функция для генерации случайного короткого кода
    def generate_short_code(self):
        return ''.join(random.choices(string.ascii_letters + string.digits, k=6))

    @action(detail=True, methods=['get'], url_path='get-link')
    def get_recipe_link(self, request, pk=None):
        recipe = self.get_object()

        # Проверяем, есть ли уже короткая ссылка для этого рецепта
        short_link, created = ShortLink.objects.get_or_create(recipe=recipe)

        if created:
            # Генерируем короткий код, если создаем новую ссылку
            short_link.short_code = self.generate_short_code()
            short_link.save()

        # Формируем полную короткую ссылку
        short_url = f"https://{settings.SITE_DOMAIN}/s/{short_link.short_code}"
        
        return Response({"short-link": short_url}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='download_shopping_cart')
    def download_shopping_cart(self, request):
        # Получаем все рецепты, добавленные в корзину пользователя
        shopping_cart = ShoppingCart.objects.filter(author=request.user)
        
        if not shopping_cart.exists():
            return Response({"detail": "Shopping cart is empty."}, status=status.HTTP_400_BAD_REQUEST)

        # Словарь для хранения суммированных ингредиентов
        ingredients_summary = {}

        # Проходим по всем рецептам в корзине
        for item in shopping_cart:
            # Получаем все ингредиенты рецепта
            recipe_ingredients = item.recipe.recipe_ingredients.all()

            for ingredient in recipe_ingredients:
                ingredient_name = ingredient.ingredient.name
                ingredient_unit = ingredient.ingredient.measurement_unit
                ingredient_amount = ingredient.amount

                # Если ингредиент уже есть в списке, суммируем его количество
                if ingredient_name in ingredients_summary:
                    ingredients_summary[ingredient_name]['amount'] += ingredient_amount
                else:
                    ingredients_summary[ingredient_name] = {
                        'amount': ingredient_amount,
                        'unit': ingredient_unit,
                    }

        # Формируем текст для файла
        content = "Ваш список покупок:\n"
        for ingredient, data in ingredients_summary.items():
            content += f"{ingredient}: {data['amount']} {data['unit']}\n"

        # Создаем текстовый файл
        response = HttpResponse(content, content_type='text/plain')
        response['Content-Disposition'] = 'attachment; filename="shopping_list.txt"'
        return response

class SubscriptionViewSet(viewsets.ModelViewSet):
    queryset = Subscription.objects.all()
    serializer_class = SubscriptionSerializer
    permission_classes = [IsAuthenticated]

    def list(self, request, *args, **kwargs):
        # Возвращаем только подписки текущего пользователя
        subscriptions = Subscription.objects.filter(user=request.user)
        page = self.paginate_queryset(subscriptions)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(subscriptions, many=True)
        return Response(serializer.data)


class FavoriteViewSet(viewsets.ModelViewSet):
    queryset = Favorite.objects.all()
    serializer_class = FavoriteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Фильтруем рецепты, которые пользователь добавил в избранное
        user = self.request.user
        return Recipe.objects.filter(favorited_recipes__author=user)

    def list(self, request):
        # Получаем избранные рецепты для текущего пользователя
        favorites = Favorite.objects.filter(author=request.user)
        recipe_ids = favorites.values_list('recipe_id', flat=True)
        recipes = Recipe.objects.filter(id__in=recipe_ids)
        serializer = RecipeSerializer(recipes, many=True)
        return Response(serializer.data)



class ShoppingCartViewSet(viewsets.ModelViewSet):
    queryset = ShoppingCart.objects.all()
    serializer_class = ShoppingCartSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        # Получаем id рецепта из URL
        recipe_id = self.kwargs.get('id')

        try:
            # Пытаемся найти рецепт по переданному ID
            recipe = Recipe.objects.get(id=recipe_id)
        except Recipe.DoesNotExist:
            return Response({"detail": "Recipe not found."}, status=status.HTTP_404_NOT_FOUND)

        # Проверяем, что рецепт еще не добавлен в корзину пользователя
        if ShoppingCart.objects.filter(author=request.user, recipe=recipe, cooking_time=recipe.cooking_time).exists():
            return Response({"detail": "Recipe already in shopping cart."}, status=status.HTTP_400_BAD_REQUEST)

        # Создаем запись в корзине покупок
        ShoppingCart.objects.create(author=request.user, recipe=recipe, cooking_time=recipe.cooking_time)
        return Response({"detail": "Recipe added to shopping cart."}, status=status.HTTP_201_CREATED)


