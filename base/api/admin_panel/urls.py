from django.urls import path
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register('users', views.AdminUserViewSet, basename='admin-users')
router.register('rooms', views.AdminRoomViewSet, basename='admin-rooms')
router.register('topics', views.AdminTopicViewSet, basename='admin-topics')
router.register('messages', views.AdminMessageViewSet, basename='admin-messages')

urlpatterns = [
  path('stats/', views.adminStats),
] + router.urls
