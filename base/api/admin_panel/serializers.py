from rest_framework.serializers import ModelSerializer, ImageField, CharField, SerializerMethodField, ValidationError
from django.contrib.auth import password_validation
from base.models import Room, Topic, Message, User
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken


class AdminUserSerializer(ModelSerializer):
  password = CharField(write_only=True, required=False)

  class Meta:
    model = User
    fields = ['id', 'email', 'username', 'name', 'bio', 'avatar', 'is_active', 'is_staff', 'is_superuser', 'date_joined', 'last_login', 'password']
    read_only_fields = ['date_joined', 'last_login']
    extra_kwargs = {
      'bio': {'allow_blank': True},
    }

  # Case-insensitive uniqueness check (DRF's built-in unique check is case-sensitive,
  # so "Foo@x.com" would slip past it and crash with a 500 on save)
  def validate_email(self, value):
    email = value.lower()
    users = User.objects.filter(email__iexact=email)
    if self.instance:
      users = users.exclude(pk=self.instance.pk)
    if users.exists():
      raise ValidationError('This email already exists')
    return email

  # Same rules as registration / UpdateUserSerializer: lowercase + case-insensitive unique
  def validate_username(self, value):
    username = value.lower()
    users = User.objects.filter(username__iexact=username)
    if self.instance:
      users = users.exclude(pk=self.instance.pk)
    if users.exists():
      raise ValidationError('This username is already taken')
    return username

  def validate_password(self, value):
    password_validation.validate_password(value)
    return value

  def validate(self, data):
    # Password is required when creating a user (optional when editing)
    if self.instance is None and not data.get('password'):
      raise ValidationError({'password': 'This field is required.'})
    return data

  def create(self, validated_data):
    password = validated_data.pop('password')
    user = User(**validated_data)
    user.set_password(password) #hashes the pass
    user.save()
    return user

  def update(self, instance, validated_data):
    password = validated_data.pop('password', None)
    user = super().update(instance, validated_data)
    if password:
      user.set_password(password)
      user.save()
      for outstanding in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=outstanding)
    return user


class AdminRoomSerializer(ModelSerializer):
  host_name = CharField(source='host.username', read_only=True, allow_null=True)
  topic_name = CharField(source='topic.name', read_only=True, allow_null=True)
  participant_names = SerializerMethodField()
  message_count = SerializerMethodField()

  def get_participant_names(self, obj):
    # Usernames, not str(user): User.__str__ returns the email (USERNAME_FIELD)
    return [user.username for user in obj.participants.all()]

  def get_message_count(self, obj):
    # List/detail come from the annotated queryset; a freshly created room doesn't
    count = getattr(obj, 'message_count', None)
    return count if count is not None else obj.message_set.count()

  class Meta:
    model = Room
    fields = '__all__'   # host, topic, participants are writable for admin
    extra_kwargs = {'topic': {'required': True, 'allow_null': False}}  # same rule as public API


class AdminTopicSerializer(ModelSerializer):
  room_count = SerializerMethodField()
  host_names = SerializerMethodField()


  class Meta:
    model = Topic
    fields = '__all__'

  def get_room_count(self, obj):
    # List/detail come from the annotated queryset; a freshly created topic doesn't,
    # so fall back to counting (0 for a new topic)
    count = getattr(obj, 'room_count', None)
    return count if count is not None else obj.room_set.count()
  def get_host_names(self, obj):
    # Unique usernames of everyone hosting a room in this topic (A-Z)
    return sorted({room.host.username for room in obj.room_set.all() if room.host})

  

  # No duplicate topics (case-insensitive), matching the public API's get-or-create
  def validate_name(self, value):
    name = value.strip()
    topics = Topic.objects.filter(name__iexact=name)
    if self.instance:
      topics = topics.exclude(pk=self.instance.pk)
    if topics.exists():
      raise ValidationError('A topic with this name already exists')
    return name


class AdminMessageSerializer(ModelSerializer):
  user_avatar = ImageField(source='user.avatar', read_only=True)
  user_name = CharField(source='user.username', read_only=True)
  room_name = CharField(source='room.name', read_only=True)

  class Meta:
    model = Message
    fields = '__all__'
    read_only_fields = ['user', 'room']   # admin can edit the body, not who wrote it or where
