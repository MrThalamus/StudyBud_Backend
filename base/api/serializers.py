from rest_framework.serializers import ModelSerializer, Serializer, CharField, EmailField, ValidationError, ImageField, IntegerField
from base.models import Room, Topic, Message, User
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth import authenticate
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class RoomSerializer(ModelSerializer):
  host_name = CharField(source='host.username', read_only=True, allow_null=True)
  host_avatar = ImageField(source='host.avatar', read_only=True, allow_null=True)
  topic_name = CharField(source='topic.name', read_only=True, allow_null=True)

  class Meta:
    model = Room
    fields = '__all__'
    read_only_fields = ['host', 'participants', 'topic']
    extra_kwargs = {'topic': {'required': True, 'allow_null': False}} #A room with no topic can be created through the API but not through the website.(Fixed)

class TopicSerializer(ModelSerializer):
  room_count = IntegerField(read_only=True)

  class Meta:
    model = Topic 
    fields = '__all__'

class MessageSerializer(ModelSerializer):
  user_name = CharField(source='user.username', read_only=True)
  user_avatar = ImageField(source='user.avatar', read_only=True)
  room_name = CharField(source='room.name', read_only=True)

  class Meta:
    model = Message  
    fields = '__all__'
    read_only_fields = ['user', 'room']

class RegisterSerializer(ModelSerializer):
  password1 = CharField(write_only=True)
  password2 = CharField(write_only=True)
  
  class Meta:
    model = User
    fields = ['id', 'name', 'username', 'email', 'password1', 'password2']

  def validate_email(self, value):
    getGmail = value.lower()
    if User.objects.filter(email__iexact=getGmail).exists():
      raise ValidationError('This email already exists')
    return getGmail
    
  def validate_username(self, value):
    username = value.lower()
    if User.objects.filter(username__iexact=username).exists():
      raise ValidationError('This username is already taken')
    return username


  def validate(self, data):
    if data['password1'] != data['password2']:
      raise ValidationError({'password2': 'Passwords do not match'})
    validate_password(data['password1'])
    return data
  
  def create(self, validated_data):
    password = validated_data.pop('password1')
    validated_data.pop('password2')
    return User.objects.create_user(password=password, **validated_data)

class UserSerializer(ModelSerializer):
  class Meta:
    model = User
    fields = ['id', 'name', 'username', 'bio', 'avatar']

class UpdateUserSerializer(ModelSerializer):
  class Meta:
    model = User
    fields = ['id', 'avatar', 'name', 'username', 'email', 'bio', 'is_superuser']
    read_only_fields = ['is_superuser']
    extra_kwargs = {
      'bio': {'allow_blank': True},
    }


  def validate_email(self, value):
    email = value.lower()
    if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
      raise ValidationError('This email already exists')
    return email

  def validate_username(self, value):
    username = value.lower()
    if User.objects.filter(username__iexact=username).exclude(pk=self.instance.pk).exists():
      raise ValidationError('This username is already taken')
    return username

class LoginSerializer(Serializer):
  email = EmailField()
  password = CharField(write_only=True, trim_whitespace=False)

  def validate(self, data):
    # USERNAME_FIELD is 'email', so authenticate() looks the user up by email
    user = authenticate(
      request=self.context.get('request'),
      email=data['email'].lower(),
      password=data['password'],
    )
    # None = wrong email/password OR inactive account (same message on purpose)
    if user is None:
      raise ValidationError('Invalid email or password.')
    data['user'] = user
    return data

class JWTLoginSerializer(TokenObtainPairSerializer):
  @classmethod
  def get_token(cls, user):
    token = super().get_token(user)
    token['username'] = user.username
    token['is_superuser'] = user.is_superuser
    return token

  def validate(self, attrs):
    attrs['email'] = attrs['email'].lower()
    data = super().validate(attrs)
    data['user'] = UpdateUserSerializer(self.user).data
    return data


    
    
