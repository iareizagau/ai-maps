from django.urls import path
from . import views

app_name = "blog"

urlpatterns = [
    path("", views.post_list, name="post_list"),
    path("category/<slug:category_slug>/", views.post_list, name="post_list_category"),
    path("tag/<slug:tag_slug>/", views.post_list, name="post_list_tag"),
    path("api/chat/", views.blog_chat_api, name="blog_chat_api"),
    path("<slug:slug>/", views.post_detail, name="post_detail"),
]
