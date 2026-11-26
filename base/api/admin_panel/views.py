from rest_framework import viewsets, filters, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import MultiPartParser
from django.db.models import Count
from ..serializers import JWTLoginSerializer
from django.db import IntegrityError, transaction
from base.models import Room, Topic, Message, User
from .permissions import IsSuperUser
from .user_import import ImportFileError, parse_upload
from .serializers import (
  AdminUserSerializer, AdminRoomSerializer, AdminTopicSerializer, AdminMessageSerializer
)

class AdminPagination(PageNumberPagination):
  page_size = 20
  page_size_query_param = 'page_size'
  max_page_size = 100


class AdminBaseViewSet(viewsets.ModelViewSet):
  permission_classes = [IsSuperUser]   # overrides global IsAuthenticatedOrReadOnly
  pagination_class = AdminPagination
  filter_backends = [filters.SearchFilter, filters.OrderingFilter]


#---------------------Users-----------------------------
class AdminUserViewSet(AdminBaseViewSet):
  queryset = User.objects.all().order_by('-date_joined')
  serializer_class = AdminUserSerializer
  search_fields = ['email', 'username', 'name']
  ordering_fields = ['id', 'date_joined', 'last_login', 'username']

  def update(self, request, *args, **kwargs):
    response = super().update(request, *args, **kwargs)
    # Changing your OWN password blacklists all your refresh tokens
    # (see AdminUserSerializer.update), so hand back a fresh pair to stay logged in
    if request.data.get('password') and str(kwargs.get('pk')) == str(request.user.pk):
      refresh = JWTLoginSerializer.get_token(request.user)
      response.data['refresh'] = str(refresh)
      response.data['access'] = str(refresh.access_token)
    return response

  def perform_update(self, serializer):
    # Admin can't remove their own admin/staff rights or deactivate themselves
    if serializer.instance == self.request.user:
      data = serializer.validated_data
      if (data.get('is_superuser') is False
          or data.get('is_staff') is False
          or data.get('is_active') is False):
        raise ValidationError({'detail': "You can't remove your own admin access or deactivate yourself."})
    serializer.save()

  def perform_destroy(self, instance):
    if instance == self.request.user:
      raise PermissionDenied("You can't delete your own account.")
    instance.delete()
# File upload
  @action(detail=False, methods=['post'], url_path='import', parser_classes=[MultiPartParser])
  def import_users(self, request):
    upload = request.FILES.get('file')
    if upload is None:
      return Response({'detail': 'No file uploaded. Send it in a form field named "file".'},
                      status=status.HTTP_400_BAD_REQUEST)

    # File -> rows. Any whole-file problem (type, size, encoding, header, limits) is a 400
    try:
      rows = parse_upload(upload)
    except ImportFileError as e:
      return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    created, errors = [], []

    def fail(row, row_errors):
      errors.append({'row': row.line, 'email': row.data['email'], 'errors': row_errors})

    for row in rows:
      if row.problem:                       # wrong number of values on this line
        fail(row, {'detail': [row.problem]})
        continue

      serializer = self.get_serializer(data=row.data)
      if not serializer.is_valid():         # same rules as the "Create user" form
        fail(row, serializer.errors)
        continue

      try:
        with transaction.atomic():
          user = serializer.save()
      except IntegrityError:                # taken by another request at the same moment
        fail(row, {'detail': ['Email or username was just taken by another request.']})
        continue

      created.append({'row': row.line, 'id': user.id, 'email': user.email})

    return Response({
      'created': len(created),
      'failed': len(errors),
      'created_users': created,
      'errors': errors,
    }, status=status.HTTP_200_OK)


#---------------------Rooms-----------------------------
class AdminRoomViewSet(AdminBaseViewSet):
    queryset = (
      Room.objects.select_related('host', 'topic')
      .prefetch_related('participants')
      .annotate(message_count=Count('message', distinct=True))
      .order_by('-updated', '-created')  # annotate() drops the model's default ordering
    )
    serializer_class = AdminRoomSerializer
    search_fields = ['name', 'description', 'topic__name', 'host__username']
    ordering_fields = ['id', 'name', 'created', 'updated', 'message_count']



#---------------------Topics-----------------------------
class AdminTopicViewSet(AdminBaseViewSet):
  queryset = (
    Topic.objects.annotate(room_count=Count('room'))
    .prefetch_related('room_set__host')  # rooms + their hosts in 2 queries total
    .order_by('name')
  )
  serializer_class = AdminTopicSerializer
  search_fields = ['name']
  ordering_fields = ['id', 'name', 'room_count']


#---------------------Messages-----------------------------
class AdminMessageViewSet(AdminBaseViewSet):
  queryset = Message.objects.select_related('user', 'room').all()
  serializer_class = AdminMessageSerializer
  search_fields = ['body', 'user__username', 'room__name']
  ordering_fields = ['id', 'created', 'updated']
  # No POST: user/room are read-only, so admin can't create messages as someone else
  http_method_names = ['get', 'put', 'patch', 'delete', 'head', 'options']


  # ?room=<id> = only that room's messages (exact match; ?search= is a fuzzy text search)
  def get_queryset(self):
    queryset = super().get_queryset()
    room = self.request.query_params.get('room')
    if room is not None:
      if not room.isdigit():
        raise ValidationError({'room': 'Must be a room id (a number).'})
      queryset = queryset.filter(room_id=room)
    return queryset

#---------------------Dashboard stats------------ 
@api_view(['GET'])
@permission_classes([IsSuperUser])
def adminStats(request):
  return Response({
    'users': User.objects.count(),
    'active_users': User.objects.filter(is_active=True).count(),
    'admins': User.objects.filter(is_superuser=True).count(),
    'rooms': Room.objects.count(),
    'topics': Topic.objects.count(),
    'messages': Message.objects.count(),
  }, status=status.HTTP_200_OK)
