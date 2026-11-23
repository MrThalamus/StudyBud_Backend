from rest_framework.pagination import LimitOffsetPagination
from rest_framework.decorators import api_view,permission_classes, authentication_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated  
from base.models import Room, Topic, Message, User
from .serializers import RoomSerializer, TopicSerializer, MessageSerializer, RegisterSerializer, UserSerializer, UpdateUserSerializer, JWTLoginSerializer
from django.shortcuts import get_object_or_404
from rest_framework import status
from django.db.models import Q, Count
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError


@api_view(['GET'])
def getRoute(request):
  routes=[
    'GET /api/',
    'POST /api/auth/login/',
    'POST /api/auth/refresh/',
    #---------------------Room-----------------------------
    'GET /api/rooms/', 
    'POST /api/rooms/', 
    'GET /api/rooms/:id/', 
    'PATCH /api/rooms/:id/update/',
    'DELETE /api/rooms/:id/delete/',
    #---------------------Topic-----------------------------
    'GET /api/topics/?q=', 
    #---------------------Messages-----------------------------
    'GET /api/rooms/:id/messages/',
    'POST /api/rooms/:id/messages/',
    'GET /api/messages/',
    'DELETE /api/messages/:id/delete/',

    #---------------------Register User------------------------
    'POST /api/register/',
    #---------------------User Profile-------------------------
    'GET /api/users/:id/',
    'GET /api/users/me/',
    'GET /api/users/:id/rooms',
    'GET /api/users/:id/messages',
    'PATCH /api/users/update/',
    #---------------------User Profile-------------------------
    'POST /api/auth/logout/',

  ]
  return Response(routes)

#---------------------Helpers-----------------------------
TOPIC_NAME_MAX_LENGTH = Topic._meta.get_field('name').max_length

def get_or_create_topic(name):
  # Case-insensitive match so "python" reuses an existing "Python" topic
  topic = Topic.objects.filter(name__iexact=name).first()
  if topic is None:
    topic = Topic.objects.create(name=name)
  return topic

#---------------------Room-----------------------------
@api_view(['GET', 'POST'])
def getRooms(request):
  if request.method == 'GET':
    q = request.GET.get('q', '').strip()
    topic = request.GET.get('topic', '').strip()
    rooms = Room.objects.select_related('host', 'topic').filter(
      Q(topic__name__icontains=q) |
      Q(name__icontains=q) |
      Q(description__icontains=q)
    )
    if topic:
      rooms = rooms.filter(topic__name__iexact=topic)  # exact topic, not a text match

    serializer = RoomSerializer(rooms, many=True)
    return Response(serializer.data)

  # POST
  if not request.user.is_authenticated:
    return Response({'detail': 'Authentication required.'}, status=status.HTTP_401_UNAUTHORIZED)

  # Admins manage rooms; only normal users can host one
  if request.user.is_admin:
    return Response({'detail': "Admins can't host rooms."}, status=status.HTTP_403_FORBIDDEN)


  topic_name = str(request.data.get('topic_name', '')).strip()
  if not topic_name:
    return Response({'topic_name': ['This field is required.']}, status=status.HTTP_400_BAD_REQUEST)
  if len(topic_name) > TOPIC_NAME_MAX_LENGTH:
    return Response({'topic_name': [f'Ensure this field has no more than {TOPIC_NAME_MAX_LENGTH} characters.']}, status=status.HTTP_400_BAD_REQUEST)

  serializer = RoomSerializer(data=request.data)
  if serializer.is_valid():
    topic = get_or_create_topic(topic_name)
    serializer.save(host=request.user, topic=topic)
    return Response(serializer.data, status=status.HTTP_201_CREATED)
  return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
def getRoomParticipants(request, pk):
  room = get_object_or_404(Room, id=pk)
  serializer = UserSerializer(room.participants.all(), many=True)
  return Response(serializer.data, status=status.HTTP_200_OK)

@api_view(['GET'])
def getRoom(request, pk):
  room = get_object_or_404(Room, id=pk)

  if request.method == 'GET':
    serializer = RoomSerializer(room, many=False)
    return Response(serializer.data)

@api_view(['PATCH'])
def updateRoom(request, pk):
   room = get_object_or_404(Room, id=pk)

   if room.host != request.user:
     return Response(status=status.HTTP_403_FORBIDDEN)

   topic_name = str(request.data.get('topic_name', '')).strip()
   if len(topic_name) > TOPIC_NAME_MAX_LENGTH:
     return Response({'topic_name': [f'Ensure this field has no more than {TOPIC_NAME_MAX_LENGTH} characters.']}, status=status.HTTP_400_BAD_REQUEST)

   serializer = RoomSerializer(room, data=request.data, partial=True)
   if serializer.is_valid():
     if topic_name:
       topic = get_or_create_topic(topic_name)
       serializer.save(topic=topic)
     else:
       serializer.save()
     return Response(serializer.data, status=status.HTTP_200_OK)
   return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
def deleteRoom(request, pk):
  room = get_object_or_404(Room, id=pk)

  if room.host != request.user:
    return Response(status=status.HTTP_403_FORBIDDEN)
  
  room.delete()
  return Response(status=status.HTTP_204_NO_CONTENT)
  
#---------------------Topic-----------------------------
@api_view(['GET'])
def getTopics(request):
  q = request.GET.get('q', '').strip()
  topics = Topic.objects.filter(name__icontains=q).annotate(room_count=Count('room'))
  serializer = TopicSerializer(topics, many=True)
  return Response(serializer.data)

#---------------------Messages-----------------------------
@api_view(['GET', 'POST'])
def getMessages(request, pk):
  room = get_object_or_404(Room, id=pk)

  if request.method == 'GET':
    messages = room.message_set.all()
    serializer = MessageSerializer(messages, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)
  
  if request.method == 'POST':
    serializer = MessageSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(user=request.user, room=room)
        room.participants.add(request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
class MessagePagination(LimitOffsetPagination):
  default_limit = 20   # used when the frontend sends no ?limit=
  max_limit = 100      # ?limit=99999 is cut down to 100


@api_view(['GET'])
def getAllMessages(request):
  messages = Message.objects.select_related('user', 'room')
  paginator = MessagePagination()
  page = paginator.paginate_queryset(messages, request)
  serializer = MessageSerializer(page, many=True)
  return paginator.get_paginated_response(serializer.data)

@api_view(['DELETE'])
def deleteMessage(request, pk):
  messages = Message.objects.all()
  message = get_object_or_404(messages, id=pk)

  if message.user != request.user:
    return Response(status=status.HTTP_403_FORBIDDEN)
  message.delete()
  return Response(status=status.HTTP_204_NO_CONTENT)


#---------------------Register-----------------------------
@api_view(['POST'])
@permission_classes([AllowAny])
def registerUser(request):
  serializer = RegisterSerializer(data=request.data)
  if serializer.is_valid():
    user = serializer.save()
    refresh = JWTLoginSerializer.get_token(user) 
    return Response(
      {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
        'user': UpdateUserSerializer(user).data,
      },
      status=status.HTTP_201_CREATED
    )

  return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

#---------------------User Profile---------------------
@api_view(['GET'])
def getUser(request, pk):
  user = get_object_or_404(User, id=pk)
  serializer = UserSerializer(user, many=False)
  return Response(serializer.data, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def getMe(request):
  serializer = UpdateUserSerializer(request.user, many=False)
  return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
def getUserRooms(request, pk):
  user = get_object_or_404(User, id=pk)
  rooms = user.room_set.all()
  serializer = RoomSerializer(rooms, many=True)
  return Response(serializer.data, status=status.HTTP_200_OK)

@api_view(['GET'])
def getUserMessages(request, pk):
  user = get_object_or_404(User, id=pk)
  messages = user.message_set.all()
  serializer = MessageSerializer(messages, many=True)
  return Response(serializer.data, status=status.HTTP_200_OK)

@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def updateUser(request):
  serializer = UpdateUserSerializer(request.user, data=request.data, partial=True)
  if serializer.is_valid():
    serializer.save()
    return Response(serializer.data, status=status.HTTP_200_OK)
  return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

#---------------------Logout-----------------------------
@api_view(['POST'])
@authentication_classes([])  # logout only needs the refresh token in the body
@permission_classes([AllowAny])
def jwtLogout(request):
  refresh = request.data.get('refresh')
  if not refresh:
    return Response({'refresh': ['This field is required.']}, status=status.HTTP_400_BAD_REQUEST)

  try:
    token = RefreshToken(refresh)
    token.blacklist()
  except TokenError:
    return Response({'detail': 'Token is invalid, expired or already logged out.'}, status=status.HTTP_400_BAD_REQUEST)

  return Response({'detail': 'Logged out successfully'}, status=status.HTTP_200_OK)
