from django.urls import path, include
from . import views
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView



urlpatterns =[
  path('', views.getRoute),

  #-----------------Admin Panel------------------------
  path('admin/', include('base.api.admin_panel.urls')),
  #---------------------Room-----------------------------
  path('rooms/', views.getRooms),
  path('rooms/<int:pk>/', views.getRoom),
  path('rooms/<int:pk>/update/', views.updateRoom),
  path('rooms/<int:pk>/delete/', views.deleteRoom),
  path('rooms/<int:pk>/participants/', views.getRoomParticipants),
  #---------------------Topic-----------------------------
  path('topics/', views.getTopics),
  #---------------------Message-----------------------------
  path('rooms/<int:pk>/messages/', views.getMessages),
  path('messages/', views.getAllMessages),
  path('messages/<int:pk>/delete/', views.deleteMessage),
  #---------------------Register User--------------------------
  path('register/', views.registerUser),
  #---------------------User Profile--------------------------
  path('users/<int:pk>/', views.getUser),
  path('users/me/', views.getMe),
  path('users/<int:pk>/rooms/', views.getUserRooms),
  path('users/<int:pk>/messages/', views.getUserMessages),
  path('users/update/', views.updateUser),
  #--------------------Logout----------------------------------
  path('auth/logout/', views.jwtLogout),
  #--------------------Login-----------------------------------
  path('auth/login/', TokenObtainPairView.as_view()),
  path('auth/refresh/', TokenRefreshView.as_view()),


  
]