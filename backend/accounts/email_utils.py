"""
Email utilities for sending emails using Resend
"""
import resend
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from decouple import config
import logging

logger = logging.getLogger(__name__)

# Initialize Resend with API key
resend.api_key = settings.RESEND_API_KEY


class EmailService:
    """Service class for handling email operations"""

    @staticmethod
    def send_email(to_email, subject, template_name, context=None):
        """
        Send an email using Resend

        Args:
            to_email: Recipient email address
            subject: Email subject
            template_name: Name of the email template
            context: Context dictionary for template rendering

        Returns:
            bool: True if email sent successfully, False otherwise
        """
        try:
            # Add default context
            default_context = {
                'site_name': settings.SITE_NAME,
                'site_url': settings.SITE_URL,
                'support_email': settings.SUPPORT_EMAIL,
            }

            if context:
                default_context.update(context)

            # Render email templates
            html_content = render_to_string(f'emails/{template_name}.html', default_context)
            text_content = strip_tags(html_content)

            # Log email attempt
            logger.info(f"Attempting to send '{subject}' email to {to_email}")

            # Send email using Resend
            response = resend.Emails.send({
                "from": f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM}>",
                "to": to_email,
                "subject": subject,
                "html": html_content,
                "text": text_content
            })

            logger.info(f"✅ Email sent successfully to {to_email} | Subject: {subject} | Response: {response}")
            print(f"\n{'='*80}")
            print(f"✅ EMAIL SENT SUCCESSFULLY")
            print(f"{'='*80}")
            print(f"To: {to_email}")
            print(f"Subject: {subject}")
            print(f"Template: {template_name}")
            print(f"Response: {response}")
            print(f"{'='*80}\n")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to send email to {to_email}: {str(e)}")
            print(f"\n{'='*80}")
            print(f"❌ EMAIL FAILED")
            print(f"{'='*80}")
            print(f"To: {to_email}")
            print(f"Subject: {subject}")
            print(f"Error: {str(e)}")
            print(f"{'='*80}\n")
            # In demo mode, we'll return False to show the error
            return False

    @staticmethod
    def send_welcome_email(user):
        """Send welcome email to new user"""
        context = {
            'user': user,
            'username': user.username,
            'first_name': user.first_name or user.username,
            'dashboard_url': f"{settings.SITE_URL}/dashboard/",
        }

        return EmailService.send_email(
            to_email=user.email,
            subject=f'Welcome to {settings.SITE_NAME}',
            template_name='welcome_email',
            context=context
        )

    @staticmethod
    def send_password_reset_email(user, reset_token):
        """Send password reset email to user"""
        context = {
            'user': user,
            'reset_link': f"{settings.SITE_URL}/auth/reset-password/{reset_token}/",
            'username': user.username,
            'first_name': user.first_name or user.username,
        }

        return EmailService.send_email(
            to_email=user.email,
            subject=f'Reset Your Password - {settings.SITE_NAME}',
            template_name='password_reset_email',
            context=context
        )

    @staticmethod
    def send_login_alert_email(user, ip_address=None, user_agent=None):
        """Send login alert email to user"""
        context = {
            'user': user,
            'username': user.username,
            'first_name': user.first_name or user.username,
            'ip_address': ip_address or 'Unknown',
            'user_agent': user_agent or 'Unknown',
        }

        return EmailService.send_email(
            to_email=user.email,
            subject=f'New Login to Your Account - {settings.SITE_NAME}',
            template_name='login_alert_email',
            context=context
        )

    @staticmethod
    def send_otp_email(user, code, purpose='signup'):
        """Send a six-digit one-time code."""
        headline, intro = {
            'signup': ('Confirm your email',
                       'Use the code below to finish setting up your account.'),
            'withdrawal': ('Authorise your withdrawal',
                           'Use the code below to authorise this withdrawal.'),
        }.get(purpose, ('Your verification code', 'Use the code below to continue.'))

        return EmailService.send_email(
            to_email=user.email,
            subject=f'{code} is your {settings.SITE_NAME} verification code',
            template_name='otp_email',
            context={
                'user': user,
                'first_name': user.first_name or user.username,
                'code': code,
                'headline': headline,
                'intro': intro,
                'expires_minutes': 10,
            },
        )
