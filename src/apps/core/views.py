from django.shortcuts import render, redirect
from django import forms
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from django.contrib import messages
from .forms import UserProfileForm, UsernameChangeForm
from .models import User, PaymentMethod, Follow, AppRegistry
from . import selectors, pulse


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')


def home(request):
    apps = AppRegistry.objects.filter(is_active=True)
    return render(request, 'home.html', {
        'apps': apps,
        'pulse_items': pulse.get_pulse_items(),
    })


def login_view(request):
    """User login"""
    if request.user.is_authenticated:
        return redirect('pintxos:index')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect('pintxos:index')
        else:
            return render(request, 'auth/login.html', {'error': 'Usuario o contraseña inválidos'})

    return render(request, 'auth/login.html')


def register_view(request):
    """User registration"""
    if request.user.is_authenticated:
        return redirect('pintxos:index')

    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('pintxos:index')
        else:
            return render(request, 'auth/register.html', {'form': form})
    else:
        form = CustomUserCreationForm()

    return render(request, 'auth/register.html', {'form': form})


@login_required
def profile(request):
    """Main user profile panel"""
    user_form = UserProfileForm(instance=request.user)
    username_form = UsernameChangeForm(instance=request.user)
    password_form = PasswordChangeForm(request.user)
    payment_methods = request.user.payment_methods.all()
    following = request.user.following_set.select_related('followed').all().order_by('app_context')
    
    # Discovery Engine
    suggested_experts = selectors.get_top_experts(exclude_user=request.user, limit=6)
    followed_ids = following.values_list('followed_id', flat=True)
    
    return render(request, 'core/profile.html', {
        'user_form': user_form,
        'username_form': username_form,
        'password_form': password_form,
        'payment_methods': payment_methods,
        'following': following,
        'suggested_experts': suggested_experts,
        'followed_ids': followed_ids,
    })



@login_required
def update_profile(request):
    """HTMX endpoint for updating personal data"""
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Perfil actualizado correctamente.')
            return render(request, 'core/partials/profile_form.html', {'user_form': form})
        return render(request, 'core/partials/profile_form.html', {'user_form': form})
    return redirect('profile')


@login_required
def update_username(request):
    """HTMX endpoint for changing username"""
    if request.method == 'POST':
        form = UsernameChangeForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Nombre de usuario cambiado.')
            return render(request, 'core/partials/username_form.html', {'username_form': form})
        return render(request, 'core/partials/username_form.html', {'username_form': form})
    return redirect('profile')


@login_required
def update_password(request):
    """HTMX endpoint for changing password"""
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Keep the user logged in
            messages.success(request, 'Contraseña actualizada.')
            return render(request, 'core/partials/password_form.html', {'password_form': PasswordChangeForm(request.user)})
        return render(request, 'core/partials/password_form.html', {'password_form': form})
    return redirect('profile')


@login_required
def add_payment_method(request):
    """Mock endpoint for adding payment method"""
    if request.method == 'POST':
        # Simulate adding a card
        PaymentMethod.objects.create(
            user=request.user,
            brand='Visa',
            last4='4242',
            exp_month=12,
            exp_year=2028,
            is_default=not request.user.payment_methods.exists()
        )
        messages.success(request, 'Método de pago añadido.')
        return render(request, 'core/partials/payment_methods.html', {
            'payment_methods': request.user.payment_methods.all()
        })
    return redirect('profile')


@login_required
def delete_payment_method(request, pk):
    """Delete a payment method"""
    method = request.user.payment_methods.filter(pk=pk).first()
    if method:
        method.delete()
        messages.success(request, 'Método de pago eliminado.')
    return render(request, 'core/partials/payment_methods.html', {
        'payment_methods': request.user.payment_methods.all()
    })


@login_required
def remove_follow(request, pk):
    """Unfollow from profile panel"""
    follow = request.user.following_set.filter(pk=pk).first()
    if follow:
        follow.delete()
        messages.success(request, 'Has dejado de seguir a este usuario.')
    
    following = request.user.following_set.select_related('followed').all().order_by('app_context')
    return render(request, 'core/partials/following_list.html', {
        'following': following
    })


@login_required
def search_users(request):
    """HTMX endpoint for searching users to follow"""
    query = request.GET.get('q', '')
    if len(query) < 2:
        return render(request, 'core/partials/user_search_results.html', {'users': []})
    
    users = User.objects.filter(username__icontains=query).exclude(id=request.user.id)[:10]
    followed_ids = Follow.objects.filter(
        follower=request.user, 
        app_context='pintxos'
    ).values_list('followed_id', flat=True)
    
    return render(request, 'core/partials/user_search_results.html', {
        'users': users,
        'followed_ids': followed_ids
    })