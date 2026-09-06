from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import SetPasswordForm
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone
from .forms import UserRegistrationForm, UserLoginForm
from .models import User, EmailOTP, PasswordResetToken, LoginHistory
from .email_utils import EmailService


def login_view(request):
    """Handle user login"""
    # Redirect if already logged in
    if request.user.is_authenticated:
        return redirect('dashboard:index')  # We'll create this later

    if request.method == 'POST':
        form = UserLoginForm(request, data=request.POST)

        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            remember_me = form.cleaned_data.get('remember_me', False)

            # Authenticate user
            user = authenticate(request, username=username, password=password)

            if user is not None:
                if not user.is_verified:
                    # Unverified accounts must finish the emailed OTP first.
                    otp = EmailOTP.issue(user, purpose='signup')
                    EmailService.send_otp_email(user, otp.code, 'signup')
                    request.session['otp_user_id'] = user.id
                    request.session['verification_email'] = user.email
                    messages.info(
                        request,
                        'Please confirm your email address. We have sent a new code to '
                        f'{user.email}.'
                    )
                    return redirect('accounts:verify_otp')

                login(request, user)

                # Set session expiry
                if not remember_me:
                    request.session.set_expiry(0)  # Session expires when browser closes
                else:
                    request.session.set_expiry(1209600)  # 2 weeks

                # Log login history
                ip_address = request.META.get('REMOTE_ADDR')
                user_agent = request.META.get('HTTP_USER_AGENT', '')
                LoginHistory.objects.create(
                    user=user,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=True
                )

                # Send login alert email (optional - can be disabled)
                # EmailService.send_login_alert_email(user, ip_address, user_agent)

                messages.success(request, f'Welcome back, {user.get_full_name()}!')

                # Honour ?next=, but only for targets on this host: an unchecked
                # value lets an attacker bounce a freshly-authenticated user to a
                # lookalike "session expired" page.
                next_url = request.GET.get('next')
                if next_url and url_has_allowed_host_and_scheme(
                        next_url,
                        allowed_hosts={request.get_host()},
                        require_https=request.is_secure()):
                    return redirect(next_url)
                return redirect('dashboard:index')
            else:
                messages.error(request, 'Invalid username or password.')
        else:
            # Check if username/email exists but password is wrong
            username = request.POST.get('username')
            if User.objects.filter(username=username).exists() or User.objects.filter(email=username).exists():
                messages.error(request, 'Invalid password. Please try again.')
            else:
                messages.error(request, 'Invalid username or password.')
    else:
        form = UserLoginForm()

    return render(request, 'auth/login.html', {'form': form})


def register_view(request):
    """Handle user registration"""
    # Redirect if already logged in
    if request.user.is_authenticated:
        return redirect('dashboard:index')

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)

        if form.is_valid():
            # Create user
            user = form.save()

            # The scraped form also collects country; keep it if supplied.
            country = (request.POST.get('country') or '').strip()
            if country:
                user.country = country
                user.save(update_fields=['country'])

            # Issue a six-digit code and email it
            otp = EmailOTP.issue(user, purpose='signup')
            email_sent = EmailService.send_otp_email(user, otp.code, 'signup')

            # Remember who we are verifying (the user is NOT logged in yet)
            request.session['otp_user_id'] = user.id
            request.session['verification_email'] = user.email
            request.session['user_name'] = user.get_full_name()

            if email_sent:
                messages.success(
                    request,
                    f'Account created. We sent a 6-digit code to {user.email}.'
                )
            else:
                messages.warning(
                    request,
                    'Account created but we could not send your verification code. '
                    'Use "Resend code" below, or contact support.'
                )

            return redirect('accounts:verify_otp')
        else:
            # Display form errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{error}')
    else:
        form = UserRegistrationForm()

    return render(request, 'auth/register.html', {'form': form})


def forgot_password_view(request):
    """Handle password reset request"""
    if request.method == 'POST':
        email = request.POST.get('email')

        # Check if email exists
        try:
            user = User.objects.get(email=email)

            # Create password reset token
            reset_token = PasswordResetToken.objects.create(user=user)

            # Send password reset email
            EmailService.send_password_reset_email(user, str(reset_token.token))

        except User.DoesNotExist:
            pass  # Don't reveal if email doesn't exist

        # Always show same message (security best practice)
        messages.success(
            request,
            'If an account with this email exists, you will receive password reset instructions shortly.'
        )

        return redirect('accounts:login')

    return render(request, 'auth/forgot-password.html')


def _otp_user(request):
    """The account currently being verified, or None."""
    uid = request.session.get('otp_user_id')
    if uid:
        return User.objects.filter(pk=uid).first()
    email = request.session.get('verification_email')
    if email:
        return User.objects.filter(email=email).first()
    return None


def verify_otp_view(request):
    """Confirm the six-digit code we emailed at registration."""
    user = _otp_user(request)
    if user is None:
        messages.error(request, 'Please register or log in first.')
        return redirect('accounts:register')

    if user.is_verified:
        messages.info(request, 'Your email is already verified. Please log in.')
        return redirect('accounts:login')

    if request.method == 'POST':
        submitted = ''.join(request.POST.get('code', '').split())
        otp = (EmailOTP.objects
               .filter(user=user, purpose='signup', is_used=False)
               .order_by('-created_at')
               .first())

        if otp is None:
            messages.error(request, 'That code is no longer valid. Request a new one.')
        else:
            ok, reason = otp.verify(submitted)
            if ok:
                user.is_verified = True
                user.save(update_fields=['is_verified'])
                EmailService.send_welcome_email(user)

                for key in ('otp_user_id', 'verification_email', 'user_name'):
                    request.session.pop(key, None)

                login(request, user,
                      backend='accounts.views.EmailOrUsernameModelBackend')
                LoginHistory.objects.create(
                    user=user,
                    ip_address=request.META.get('REMOTE_ADDR'),
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    success=True,
                )
                messages.success(request, 'Your email is verified. Welcome aboard!')
                return redirect('dashboard:index')
            messages.error(request, reason)

    return render(request, 'auth/verify-otp.html', {
        'email': user.email,
        'user_name': user.get_full_name() or user.username,
    })


def reset_password_view(request, token):
    """Handle password reset"""
    try:
        reset_token = PasswordResetToken.objects.get(token=token)

        if not reset_token.is_valid():
            messages.error(
                request,
                'This password reset link has expired or been used. Please request a new one.'
            )
            return redirect('accounts:forgot_password')

        if request.method == 'POST':
            form = SetPasswordForm(reset_token.user, request.POST)

            if form.is_valid():
                form.save()
                reset_token.mark_as_used()

                messages.success(
                    request,
                    'Your password has been reset successfully. You can now log in with your new password.'
                )
                return redirect('accounts:login')
        else:
            form = SetPasswordForm(reset_token.user)

        return render(request, 'auth/reset-password.html', {
            'form': form,
            'token': token
        })

    except PasswordResetToken.DoesNotExist:
        messages.error(request, 'Invalid password reset link.')
        return redirect('accounts:forgot_password')


@login_required
def logout_view(request):
    """Handle user logout"""
    user_name = request.user.get_full_name()
    logout(request)
    messages.success(request, f'Goodbye, {user_name}! You have been logged out successfully.')
    return redirect('accounts:login')


def verify_email_sent_view(request):
    """Kept for old links; the code screen is the real destination."""
    return redirect('accounts:verify_otp')


def resend_verification_email(request):
    """Resend verification email to user"""
    # Get email from session or logged in user
    if request.user.is_authenticated:
        user = request.user
    else:
        email = request.session.get('verification_email')
        if not email:
            messages.error(request, 'Please register first.')
            return redirect('accounts:register')

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            messages.error(request, 'User not found.')
            return redirect('accounts:register')

    if user.is_verified:
        messages.info(request, 'Your email is already verified.')
        return redirect('accounts:login')

    # Rate-limit resends to one per minute
    last = (EmailOTP.objects.filter(user=user, purpose='signup')
            .order_by('-created_at').first())
    if last and (timezone.now() - last.created_at).total_seconds() < 60:
        wait = 60 - int((timezone.now() - last.created_at).total_seconds())
        messages.info(request, f'Please wait {wait}s before requesting another code.')
        return redirect('accounts:verify_otp')

    otp = EmailOTP.issue(user, purpose='signup')
    EmailService.send_otp_email(user, otp.code, 'signup')
    request.session['otp_user_id'] = user.id
    request.session['verification_email'] = user.email

    messages.success(request, f'A new code is on its way to {user.email}.')
    return redirect('accounts:verify_otp')


# Backend authentication (allows login with email)
class EmailOrUsernameModelBackend:
    """
    Custom authentication backend that allows users to log in with either username or email
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            # Try to fetch the user by email first
            user = User.objects.get(email=username)
        except User.DoesNotExist:
            try:
                # Try to fetch the user by username
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                return None

        # Check password
        if user.check_password(password):
            return user
        return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
