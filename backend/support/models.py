from django.db import models
from accounts.models import User


class SupportTicket(models.Model):
    """Model for customer support tickets"""

    STATUS_CHOICES = [
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('waiting_reply', 'Waiting for Reply'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]

    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]

    CATEGORY_CHOICES = [
        ('account', 'Account Issue'),
        ('deposit', 'Deposit Issue'),
        ('withdrawal', 'Withdrawal Issue'),
        ('investment', 'Investment Issue'),
        ('technical', 'Technical Issue'),
        ('general', 'General Inquiry'),
        ('other', 'Other'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='support_tickets')

    # Ticket details
    ticket_number = models.CharField(max_length=20, unique=True, editable=False)
    subject = models.CharField(max_length=200)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='general')
    message = models.TextField()

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')

    # Response
    admin_response = models.TextField(blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Support Ticket'
        verbose_name_plural = 'Support Tickets'
        ordering = ['-created_at']

    def __str__(self):
        return f"#{self.ticket_number} - {self.subject}"

    def save(self, *args, **kwargs):
        # Generate ticket number if not exists
        if not self.ticket_number:
            import random
            import string
            while True:
                ticket_num = 'TKT-' + ''.join(random.choices(string.digits, k=8))
                if not SupportTicket.objects.filter(ticket_number=ticket_num).exists():
                    self.ticket_number = ticket_num
                    break
        super().save(*args, **kwargs)

    def close(self):
        """Close the ticket"""
        from django.utils import timezone
        self.status = 'closed'
        if not self.resolved_at:
            self.resolved_at = timezone.now()
        self.save()

    def reopen(self):
        """Reopen a closed ticket"""
        self.status = 'open'
        self.save()


class EmailLog(models.Model):
    """Log of all emails sent from the admin panel"""
    recipient = models.EmailField()
    recipient_name = models.CharField(max_length=200)
    subject = models.CharField(max_length=300)
    template = models.CharField(max_length=100)
    content = models.TextField()
    sent = models.BooleanField(default=False)
    error_message = models.TextField(blank=True, null=True)
    sent_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='emails_sent'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Email Log'
        verbose_name_plural = 'Email Logs'

    def __str__(self):
        return f"Email to {self.recipient} - {self.subject}"
