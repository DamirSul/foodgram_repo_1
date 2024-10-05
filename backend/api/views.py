from django.shortcuts import render
from djoser import views as djoser_views
from rest_framework import status, viewsets, permissions
from rest_framework.response import Response

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, AllowAny

from food.models import Ingredient, Tag, Recipe, Subscription, Favorite, ShoppingCart
from users.models import User
from .serializers import IngredientSerializer, TagSerializer, RecipeSerializer, FavoriteSerializer, UserSerializer, ShoppingCartSerializer
from rest_framework.decorators import action
from .pagination import RecipePagination, SubscriptionPagination
from django.http import HttpResponse
from django.conf import settings
import random
import string
from food.models import ShortLink
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.core.files.base import ContentFile
import base64
from django.db.models import Exists, OuterRef

class UserViewSet(djoser_views.UserViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer 
    permission_classes = [AllowAny]

    @action(detail=False, methods=['get'], url_path='me', permission_classes=[AllowAny])
    def me(self, request):

        if not request.user.is_authenticated:
            return Response({'detail': 'Authentication credentials were not provided.'}, status=status.HTTP_401_UNAUTHORIZED)

        user = request.user
        serializer = UserSerializer(user, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


    @action(detail=False, methods=['put', 'delete'], url_path='me/avatar', permission_classes=[IsAuthenticated])
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
        
        if request.method == 'DELETE':
            user.save()
            # Формируем полный URL для ответа
            avatar_url = request.build_absolute_uri(user.avatar.url)
            
            return Response({'avatar': avatar_url}, status=status.HTTP_204_NO_CONTENT)

        
        return Response({'detail': 'No avatar provided.'}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post', 'delete'])
    def subscribe(self, request, id=None):
        try:
            author = self.get_object()
        except User.DoesNotExist:
            return Response({"detail": "Пользователь не найден."}, status=status.HTTP_404_NOT_FOUND)

        user = request.user

        if request.method == 'POST':
            if Subscription.objects.filter(user=user, author=author).exists():
                return Response({"detail": "Вы уже подписаны на этого автора."}, status=status.HTTP_400_BAD_REQUEST)

            # Создаем подписку
            subscription = Subscription.objects.create(user=user, author=author)
            serializer = UserSerializer(author, context={'request': request})
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        elif request.method == 'DELETE':
            subscription = Subscription.objects.filter(user=user, author=author).first()
            if not subscription:
                return Response({"detail": "Вы не подписаны на этого автора."}, status=status.HTTP_400_BAD_REQUEST)

            # Удаляем подписку
            subscription.delete()
            return Response({"detail": "Вы успешно отписались от автора."}, status=status.HTTP_204_NO_CONTENT)
        
    @action(detail=False, methods=['get'], pagination_class=SubscriptionPagination)
    def subscriptions(self, request):
        # Получаем подписки для пользователя и сортируем по 'id'
        subscriptions = Subscription.objects.filter(user=request.user).order_by('id')

        # Создаем пагинатор и пейджер
        paginator = self.paginator
        paginated_subscriptions = paginator.paginate_queryset(subscriptions, request)

        if not paginated_subscriptions:
            return paginator.get_paginated_response([])

        # Сериализуем информацию о пользователях
        serializer = UserSerializer(
            [subscription.author for subscription in paginated_subscriptions],
            many=True,
            context={'request': request}
        )

        return paginator.get_paginated_response(serializer.data)


class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    pagination_class = None

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



from django.db.models import Exists, OuterRef

class RecipeViewSet(viewsets.ModelViewSet):
    queryset = Recipe.objects.all().order_by('name')
    serializer_class = RecipeSerializer
    pagination_class = RecipePagination
    permission_classes = [AllowAny]

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def get_queryset(self):
        user = self.request.user
        queryset = super().get_queryset()

        # Аннотация для избранного (без конфликта с полем модели)
        if user.is_authenticated:
            queryset = queryset.annotate(
                is_recipe_favorited=Exists(Favorite.objects.filter(author=user, recipe=OuterRef('pk')))
            )

            # Аннотация для списка покупок (без конфликта с полем модели)
            queryset = queryset.annotate(
                is_in_user_shopping_cart=Exists(ShoppingCart.objects.filter(author=user, recipe=OuterRef('pk')))
            )
        else:
            # Если пользователь не авторизован, по умолчанию флаги false
            queryset = queryset.annotate(
                is_recipe_favorited=False,
                is_in_user_shopping_cart=False
            )

        # Фильтрация по параметрам
        if self.request.query_params.get('is_favorited') in ['1', 'true']:
            queryset = queryset.filter(is_recipe_favorited=True)

        if self.request.query_params.get('is_in_shopping_cart') in ['1', 'true']:
            queryset = queryset.filter(is_in_user_shopping_cart=True)

        # Фильтрация по тегам
        tag_slugs = self.request.query_params.getlist('tags')
        if tag_slugs:
            queryset = queryset.filter(tags__slug__in=tag_slugs).distinct()

        return queryset

    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context


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


    @action(detail=True, methods=['post', 'delete'], url_path='favorite')
    def toggle_favorite(self, request, pk=None):
        recipe = self.get_object()  # Получаем рецепт по первичному ключу
        user = request.user

        # Проверяем, что пользователь аутентифицирован
        if not user.is_authenticated:
            return Response({"detail": "Необходима аутентификация."}, status=status.HTTP_401_UNAUTHORIZED)

        # Проверяем, что рецепт уже в избранном
        favorite = Favorite.objects.filter(author=user, recipe=recipe).first()

        if favorite:
            # Если рецепт уже в избранном, удаляем его
            favorite.delete()
            return Response({"detail": "Рецепт успешно удален из избранного."}, status=status.HTTP_204_NO_CONTENT)
        else:
            # Если рецепт не в избранном, добавляем его
            Favorite.objects.create(author=user, recipe=recipe)
            return Response({"detail": "Рецепт добавлен в избранное."}, status=status.HTTP_201_CREATED)


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
    
    @action(detail=True, methods=['post', 'delete'], permission_classes=[IsAuthenticated])
    def shopping_cart(self, request, pk=None):
        recipe = self.get_object()
        user = request.user

        if not user.is_authenticated:
            return Response({"detail": "Необходима аутентификация."}, status=status.HTTP_401_UNAUTHORIZED)

        if request.method == 'POST':
            if ShoppingCart.objects.filter(author=user, recipe=recipe).exists():
                return Response({'detail': 'Этот рецепт уже в списке покупок.'}, status=status.HTTP_400_BAD_REQUEST)
            
            ShoppingCart.objects.create(author=user, recipe=recipe)
            response_data = {
                "id": recipe.id,
                "name": recipe.name,
                "image": request.build_absolute_uri(recipe.image.url),
                "cooking_time": recipe.cooking_time
            }
            return Response(response_data, status=status.HTTP_201_CREATED)

        elif request.method == 'DELETE':
            shopping_cart_item = ShoppingCart.objects.filter(author=user, recipe=recipe).first()
            if not shopping_cart_item:
                return Response({'detail': 'Этот рецепт не был в списке покупок.'}, status=status.HTTP_400_BAD_REQUEST)
            
            shopping_cart_item.delete()
            return Response({'detail': 'Рецепт удален из списка покупок.'}, status=status.HTTP_204_NO_CONTENT)


class FavoriteViewSet(viewsets.ModelViewSet):
    queryset = Favorite.objects.all()
    serializer_class = FavoriteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        favorite_ids = Favorite.objects.filter(author=user).values_list('recipe_id', flat=True)
        return Recipe.objects.filter(id__in=favorite_ids)




class ShoppingCartViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Получаем рецепты, добавленные в список покупок текущего пользователя
        return Recipe.objects.filter(in_shopping_cart__author=self.request.user)

    def list(self, request, *args, **kwargs):
        # Получаем все рецепты из списка покупок
        recipes = self.get_queryset()
        serializer = RecipeSerializer(recipes, many=True)
        return Response(serializer.data)