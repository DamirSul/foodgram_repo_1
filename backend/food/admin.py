from django.contrib import admin


from food.models import *

admin.site.register(
    (
    Tag,
    Recipe,
    ShoppingCart,
    Favorite,
    Subscription,
    Ingredient,
    RecipeIngredient,
    RecipeTag
    )
)