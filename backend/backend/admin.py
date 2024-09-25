from django.contrib import admin

from users.models import User
from food.models import *

admin.site.register(
    (User,
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