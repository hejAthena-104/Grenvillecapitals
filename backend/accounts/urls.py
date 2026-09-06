from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('verify/', views.verify_otp_view, name='verify_otp'),
    path('verify-email-sent/', views.verify_email_sent_view, name='verify_email_sent'),
    path('forgot-password/', views.forgot_password_view, name='forgot_password'),
    path('reset-password/<uuid:token>/', views.reset_password_view, name='reset_password'),
    path('resend-verification/', views.resend_verification_email, name='resend_verification'),
    path('logout/', views.logout_view, name='logout'),
]
