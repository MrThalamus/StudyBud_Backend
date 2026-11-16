from rest_framework.decorators import api_view,permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated  
from base.models import Room, Topic, Message, User
from .serializers import RoomSerializer, TopicSerializer, MessageSerializer, RegisterSerializer, UserSerializer, UpdateUserSerializer, LoginSerializer
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.authtoken.models import Token
from django.contrib.auth.models import update_last_login
from django.db.models import Q, Count



@api_view(['GET'])
def getRoute(request):
  routes=[
    'GET /api/',
    'POST /api/login/',


    #---------------------Room-----------------------------
    'GET /api/rooms/', #get room
    'POST /api/rooms/', #create room
    'GET /api/rooms/:id/', #get specific room
    'PATCH /api/rooms/:id/update/', #update a specific room 
    'DELETE /api/rooms/:id/delete/', #delete a specific room

    #---------------------Topic-----------------------------
    'GET /api/topics/?q=', #get topics

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
    'POST /api/logout/',

            


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

@api_view(['GET'])
def getAllMessages(request):
  messages = Message.objects.select_related('user', 'room')[:5]
  serializer = MessageSerializer(messages, many=True)
  return Response(serializer.data, status=status.HTTP_200_OK)

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
    token, created = Token.objects.get_or_create(user=user)
    return Response(
      {'token': token.key, 'user': serializer.data},
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
@permission_classes([IsAuthenticated])
def logoutUser(request):
  Token.objects.filter(user=request.user).delete()
  return Response({'detail': 'Logged out successfully'}, status=status.HTTP_200_OK)

#---------------------Login-----------------------------
@api_view(['POST'])
@permission_classes([AllowAny])
def loginUser(request):
  serializer = LoginSerializer(data=request.data, context={'request': request})
  serializer.is_valid(raise_exception=True)
  user = serializer.validated_data['user']

  token, _ = Token.objects.get_or_create(user=user)
  update_last_login(None, user)  # keeps "last login" accurate for API logins
  return Response({'token': token.key}, status=status.HTTP_200_OK)
