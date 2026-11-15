from rest_framework.serializers import ModelSerializer, CharField, IntegerField
from rest_framework.authtoken.models import Token
from django.contrib.auth import password_validation
from base.models import Room, Topic, Message, User


class AdminUserSerializer(ModelSerializer):
  password = CharField(write_only=True, required=False)

  class Meta:
    model = User
    fields = ['id', 'email', 'username', 'name', 'bio', 'avatar',
              'is_active', 'is_staff', 'is_superuser',
              'date_joined', 'last_login', 'password']
    read_only_fields = ['date_joined', 'last_login']
    extra_kwargs = {
      'bio': {'allow_blank': True},
    }

  def validate_email(self, value):
    return value.lower()

  def validate_password(self, value):
    password_validation.validate_password(value)
    return value

  def create(self, validated_data):
    password = validated_data.pop('password', None)
    user = User(**validated_data)
    if password:
      user.set_password(password) #hashes the pass
    else:
      user.set_unusable_password()
    user.save()
    return user

  def update(self, instance, validated_data):
    password = validated_data.pop('password', None)
    user = super().update(instance, validated_data)
    if password:
      user.set_password(password)
      user.save()
      Token.objects.filter(user=user).delete()  # force re-login with new password
    return user


class AdminRoomSerializer(ModelSerializer):
  host_name = CharField(source='host.username', read_only=True, allow_null=True)
  topic_name = CharField(source='topic.name', read_only=True, allow_null=True)

  class Meta:
    model = Room
    fields = '__all__'   # host, topic, participants are writable for admin


class AdminTopicSerializer(ModelSerializer):
  room_count = IntegerField(read_only=True)

  class Meta:
    model = Topic
    fields = '__all__'


class AdminMessageSerializer(ModelSerializer):
  user_name = CharField(source='user.username', read_only=True)
  room_name = CharField(source='room.name', read_only=True)

  class Meta:
    model = Message
    fields = '__all__'   # user and room are writable for admin
