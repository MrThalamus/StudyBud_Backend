from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import UserCreationForm
from django.http import HttpResponse 
from .models import Room, Topic, Message, User
from .forms import RoomForm, UserForm, MyUserCreationForm
from django.shortcuts import get_object_or_404

# Create your views here.

# rooms = [
#     {'id':1, 'name': 'Lets learn python!'},
#     {'id':2, 'name': 'Design with me'},
#     {'id':3, 'name': 'Frontend developer'},
            
# ]
def LoginPage(request):
    page = 'login'
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        email = request.POST.get('email', '').lower()
        password = request.POST.get('password') 

        if not email:
            messages.error(request, 'Please enter your email')  
        else:              
            user = authenticate(request, email=email, password=password)

            if user is not None:
                login(request, user)
                return redirect('home')
            else:
                messages.error(request, 'User or password does not exist')
    return render(request, 'base/login_register.html', {'page': page})

def logoutUser(request):
    logout(request)
    return redirect('login')

def registerPage(request):
    # page = 'register'
    form = MyUserCreationForm()
    # context = {'form': form}
    if request.method == 'POST':
        form = MyUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.username = user.username.lower()
            user.email = user.email.lower()
            user.save()
            login(request, user)
            return redirect('home')
        else:
            messages.error(request, 'An error occured during registration')
    return render(request, 'base/login_register.html', {'form': form})

def home(request):
    # return HttpResponse('Home page')
    q = request.GET.get('q') if request.GET.get('q') != None else ''
    topics = Topic.objects.all()[0:5]
    rooms = Room.objects.filter(
        Q(topic__name__icontains=q) |
        Q(name__icontains=q) |
        Q(description__icontains=q)
    )  

    room_count = rooms.count()
    room_messages = Message.objects.filter(Q(room__topic__name__icontains=q))
    context = {'rooms':rooms, 'topics': topics, 'room_count': room_count, 'room_messages': room_messages}
    return render(request, 'base/home.html', context)

def room(request, pk):
    # return HttpResponse('ROOM')
    # room = None
    # for i in rooms:
    #     if i['id'] == int(pk):
    #         room = i 
    rooms = get_object_or_404(Room, id=pk)
    room_messages = rooms.message_set.all()
    participants = rooms.participants.all()

    if request.method == 'POST':
        if not request.user.is_authenticated:
            return redirect('login')
        message = Message.objects.create(
            user = request.user,
            room=rooms,
            body=request.POST.get('body')
        )
        rooms.participants.add(request.user)
        return redirect('room', pk=rooms.id)

    context = {'room': rooms, 'room_messages': room_messages, 'participants': participants}
    return render(request, 'base/room.html', context)

def userProfile(request, pk):
    user = get_object_or_404(User, id=pk)
    rooms = user.room_set.all()
    room_messages = user.message_set.all()
    topics = Topic.objects.all()
    context = {'user': user, 'rooms': rooms, 'room_messages': room_messages, 'topics': topics}
    return render(request, 'base/profile.html', context)

@login_required(login_url='login')
def createRoom(request):
    form = RoomForm()
    topics = Topic.objects.all()

    if request.method == 'POST':
        topic_name = request.POST.get('topic')
        topic, created = Topic.objects.get_or_create(name=topic_name)

        Room.objects.create(
            host = request.user,
            topic = topic,
            name = request.POST.get('name'),
            description = request.POST.get('description')
        )
       
        return redirect('home')
    context ={'form': form, 'topics': topics }
    return render(request, 'base/room_form.html',context)

@login_required(login_url='login')
def updateRoom(request, pk):
    room = get_object_or_404(Room, id=pk)
    form = RoomForm(instance=room)
    topics = Topic.objects.all()

    if request.user != room.host:
        return HttpResponse('You are not allowed here!!')


    if request.method == 'POST':
        topic_name = request.POST.get('topic')
        topic, created = Topic.objects.get_or_create(name=topic_name)
        room.name = request.POST.get('name')
        room.topic = topic 
        room.description = request.POST.get('description')
        room.save()
        return redirect('room', pk=room.id)

    context = {'form': form, 'topics': topics, 'room': room}
    return render(request, 'base/room_form.html', context)

@login_required(login_url='login')
def deleteRoom(request, pk):
    room = get_object_or_404(Room, id=pk)

    if request.user != room.host:
            return HttpResponse('You are not allowed here!!')
    
    if request.method == 'POST':
        room.delete()
        return redirect('home')
    return render(request, 'base/delete.html', {'obj': room})

@login_required(login_url='login')
def deleteMessage(request, pk):
    message = get_object_or_404(Message, id=pk)

    if request.user != message.user:
            return HttpResponse('You are not allowed here!!')
    
    if request.method == 'POST':
        message.delete()
        return redirect('room', pk=message.room.id)
    return render(request, 'base/delete.html', {'obj': message})


@login_required(login_url='login')
def updateUser(request):
    user = request.user
    form = UserForm(instance=user)

    if request.method=='POST':
        form = UserForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            return redirect('user-profile', pk=user.id)

    return render(request, 'base/update-user.html', {'form': form})

def topicsPage(request):
    q = request.GET.get('q') if request.GET.get('q') != None else ''
    topics = Topic.objects.filter(name__icontains=q)
    return render(request, 'base/topics.html', {'topics': topics})

def activityPage(request):
    room_messages = Message.objects.all()
    return render(request, 'base/activity.html', {'room_messages': room_messages})