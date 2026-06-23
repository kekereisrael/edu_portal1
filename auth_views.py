"""
Authentication views for the frontend.
Handles login, registration, logout, forgot password, and change password.
Includes role-based redirection after login.
"""

from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from accounts.models import User


def get_role_redirect_url(user):
    """
    Get the redirect URL based on user role.
    
    Student -> /student/dashboard/
    Teacher -> /teacher/dashboard/
    Admin   -> /admin-dashboard/
    """
    if user.role == User.Role.PLATFORM_ADMIN or user.role == User.Role.SCHOOL_ADMIN:
        return '/admin-dashboard/'
    elif user.role == User.Role.TEACHER:
        return '/teacher/dashboard/'
    else:
        return '/student/dashboard/'


def login_view(request):
    """Handle user login with email and password."""
    if request.user.is_authenticated:
        return redirect(get_role_redirect_url(request.user))

    context = {}

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        remember_me = request.POST.get('remember_me')
        next_url = request.POST.get('next', '')

        if not email or not password:
            context['error'] = 'Please enter both email and password.'
            context['email'] = email
            return render(request, 'auth/login.html', context)

        user = authenticate(request, email=email, password=password)

        if user is not None:
            login(request, user)

            # Set session expiry based on remember me
            if not remember_me:
                request.session.set_expiry(0)  # Browser close
            else:
                request.session.set_expiry(1209600)  # 2 weeks

            # Redirect to next URL or role-based dashboard
            if next_url:
                return redirect(next_url)
            return redirect(get_role_redirect_url(user))
        else:
            context['error'] = 'Invalid email or password. Please try again.'
            context['email'] = email

    context['next'] = request.GET.get('next', '')
    return render(request, 'auth/login.html', context)


def register_view(request):
    """Handle user registration."""
    if request.user.is_authenticated:
        return redirect(get_role_redirect_url(request.user))

    context = {}

    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        role = request.POST.get('role', 'student')
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')
        terms = request.POST.get('terms')

        # Store form data for re-rendering
        form_data = {
            'first_name': first_name,
            'last_name': last_name,
            'email': email,
            'phone': phone,
            'role': role,
        }
        context['form_data'] = form_data

        errors = []

        # Validation
        if not first_name or not last_name:
            errors.append('First name and last name are required.')

        if not email:
            errors.append('Email address is required.')
        elif User.objects.filter(email=email).exists():
            errors.append('An account with this email already exists.')

        if not password1:
            errors.append('Password is required.')
        elif password1 != password2:
            errors.append('Passwords do not match.')
        else:
            try:
                validate_password(password1)
            except ValidationError as e:
                errors.extend(e.messages)

        if role not in ('student', 'teacher'):
            errors.append('Please select a valid role.')

        if not terms:
            errors.append('You must agree to the Terms of Service.')

        if errors:
            context['errors'] = errors
            return render(request, 'auth/register.html', context)

        # Create user
        try:
            user = User.objects.create_user(
                email=email,
                password=password1,
                first_name=first_name,
                last_name=last_name,
                role=role,
                phone=phone or None,
            )

            # Handle avatar upload
            if request.FILES.get('avatar'):
                user.avatar = request.FILES['avatar']
                user.save(update_fields=['avatar'])

            # Auto-login after registration
            login(request, user)
            messages.success(request, 'Account created successfully! Welcome to EduPortal.')
            return redirect(get_role_redirect_url(user))

        except Exception as e:
            context['errors'] = [f'Registration failed: {str(e)}']
            return render(request, 'auth/register.html', context)

    return render(request, 'auth/register.html', context)


def logout_view(request):
    """Handle user logout."""
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('auth_login')


def forgot_password_view(request):
    """Handle forgot password - send reset email."""
    context = {}

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()

        if not email:
            context['error'] = 'Please enter your email address.'
            return render(request, 'auth/forgot_password.html', context)

        # Always show success message (don't reveal if email exists)
        try:
            user = User.objects.get(email=email)
            # In production, send actual reset email here
            # For now, just show success message
            from accounts.models import PasswordResetToken
            ip_address = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() or \
                         request.META.get('REMOTE_ADDR', '127.0.0.1')
            try:
                token = PasswordResetToken.create_for_user(user, ip_address)
                # TODO: Send email with reset link
            except ValueError as e:
                context['error'] = str(e)
                return render(request, 'auth/forgot_password.html', context)
        except User.DoesNotExist:
            pass  # Don't reveal if email exists

        context['success'] = 'If an account with that email exists, we\'ve sent a password reset link.'

    return render(request, 'auth/forgot_password.html', context)


@login_required(login_url='/auth/login/')
def change_password_view(request):
    """Handle password change for authenticated users."""
    context = {}

    if request.method == 'POST':
        current_password = request.POST.get('current_password', '')
        new_password1 = request.POST.get('new_password1', '')
        new_password2 = request.POST.get('new_password2', '')

        if not request.user.check_password(current_password):
            context['error'] = 'Current password is incorrect.'
            return render(request, 'auth/change_password.html', context)

        if new_password1 != new_password2:
            context['error'] = 'New passwords do not match.'
            return render(request, 'auth/change_password.html', context)

        try:
            validate_password(new_password1, request.user)
        except ValidationError as e:
            context['error'] = ' '.join(e.messages)
            return render(request, 'auth/change_password.html', context)

        request.user.set_password(new_password1)
        request.user.save()
        update_session_auth_hash(request, request.user)
        context['success'] = 'Password updated successfully!'

    return render(request, 'auth/change_password.html', context)
