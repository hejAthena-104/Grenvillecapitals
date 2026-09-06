import random
from django.db import models
from django.utils import timezone
from accounts.models import User


STATUS_CHOICES = [
    ('pending', 'Pending'),
    ('approved', 'Approved'),
    ('rejected', 'Rejected'),
]


def _notify(user, title, message, ntype='system'):
    """Create an in-app notification (best-effort)."""
    try:
        from accounts.models import Notification
        Notification.objects.create(user=user, title=title, message=message, type=ntype)
    except Exception:
        pass


def _credit_balance(user, amount, ttype, description):
    """Disburse funds to the user's balance via a Transaction, reusing approve()."""
    from transactions.models import Transaction
    txn = Transaction.objects.create(
        user=user, type=ttype, amount=amount, status='pending', description=description,
    )
    txn.approve()
    return txn


class LoanApplication(models.Model):
    """User loan request — admin reviews; approval disburses to balance."""
    PURPOSE_CHOICES = [
        ('personal', 'Personal'),
        ('business', 'Business'),
        ('education', 'Education'),
        ('medical', 'Medical'),
        ('home', 'Home / Mortgage'),
        ('auto', 'Auto'),
        ('other', 'Other'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='loan_applications')
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    purpose = models.CharField(max_length=20, choices=PURPOSE_CHOICES, default='personal')
    term_months = models.PositiveIntegerField(default=12, help_text="Repayment term in months")
    monthly_income = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    employment_status = models.CharField(max_length=100, blank=True)
    details = models.TextField(blank=True, help_text="Additional information from the applicant")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Loan Application'
        verbose_name_plural = 'Loan Applications'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - Loan ${self.amount} - {self.status}"

    def approve(self):
        if self.status != 'pending':
            return False
        self.status = 'approved'
        self.processed_at = timezone.now()
        self.save()
        _credit_balance(self.user, self.amount, 'loan', f'Loan disbursement (#{self.pk})')
        _notify(self.user, 'Loan Approved',
                f'Your loan of ${self.amount} has been approved and credited to your balance.', 'system')
        return True

    def reject(self, reason=''):
        self.status = 'rejected'
        self.admin_note = reason
        self.processed_at = timezone.now()
        self.save()
        _notify(self.user, 'Loan Declined',
                f'Your loan application of ${self.amount} was declined. {reason}'.strip(), 'system')


class GrantApplication(models.Model):
    """Grant request as an individual or a business — admin reviews; approval disburses."""
    APPLICANT_CHOICES = [
        ('individual', 'Individual'),
        ('business', 'Business'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='grant_applications')
    applicant_type = models.CharField(max_length=20, choices=APPLICANT_CHOICES, default='individual')
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    purpose = models.CharField(max_length=255)
    details = models.TextField(blank=True)

    # Individual
    full_name = models.CharField(max_length=150, blank=True)
    # Business
    business_name = models.CharField(max_length=200, blank=True)
    registration_number = models.CharField(max_length=100, blank=True)
    business_type = models.CharField(max_length=100, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Grant Application'
        verbose_name_plural = 'Grant Applications'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - Grant ${self.amount} ({self.applicant_type}) - {self.status}"

    def approve(self):
        if self.status != 'pending':
            return False
        self.status = 'approved'
        self.processed_at = timezone.now()
        self.save()
        _credit_balance(self.user, self.amount, 'grant', f'Grant disbursement (#{self.pk})')
        _notify(self.user, 'Grant Approved',
                f'Your grant of ${self.amount} has been approved and credited to your balance.', 'system')
        return True

    def reject(self, reason=''):
        self.status = 'rejected'
        self.admin_note = reason
        self.processed_at = timezone.now()
        self.save()
        _notify(self.user, 'Grant Declined',
                f'Your grant application of ${self.amount} was declined. {reason}'.strip(), 'system')


class CardApplication(models.Model):
    """Card application — admin reviews; approval issues a demo virtual card."""
    CARD_TYPE_CHOICES = [
        ('virtual_debit', 'Virtual Debit'),
        ('virtual_credit', 'Virtual Credit'),
        ('physical_debit', 'Physical Debit'),
        ('physical_credit', 'Physical Credit'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='card_applications')
    card_type = models.CharField(max_length=20, choices=CARD_TYPE_CHOICES, default='virtual_debit')
    card_brand = models.CharField(max_length=20, default='Visa')
    full_name = models.CharField(max_length=150, blank=True, help_text="Name to print on the card")
    delivery_address = models.TextField(blank=True, help_text="For physical cards")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Card Application'
        verbose_name_plural = 'Card Applications'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.get_card_type_display()} - {self.status}"

    def approve(self):
        if self.status != 'pending':
            return False
        self.status = 'approved'
        self.processed_at = timezone.now()
        self.save()
        # Issue the card if not already issued for this application
        if not hasattr(self, 'card'):
            Card.objects.create(
                user=self.user,
                application=self,
                card_type=self.card_type,
                card_brand=self.card_brand,
                card_holder=self.full_name or self.user.get_full_name(),
            )
        _notify(self.user, 'Card Approved',
                f'Your {self.get_card_type_display()} card application was approved.', 'system')
        return True

    def reject(self, reason=''):
        self.status = 'rejected'
        self.admin_note = reason
        self.processed_at = timezone.now()
        self.save()
        _notify(self.user, 'Card Declined',
                f'Your card application was declined. {reason}'.strip(), 'system')


class Card(models.Model):
    """A demo virtual card issued on approval. Number is fabricated for display only."""
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('frozen', 'Frozen'),
        ('blocked', 'Blocked'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cards')
    application = models.OneToOneField(CardApplication, on_delete=models.CASCADE, related_name='card', null=True, blank=True)

    card_type = models.CharField(max_length=20, default='virtual_debit')
    card_brand = models.CharField(max_length=20, default='Visa')
    card_holder = models.CharField(max_length=150, blank=True)
    card_number = models.CharField(max_length=19, blank=True, help_text="Demo card number (display only)")
    expiry = models.CharField(max_length=7, blank=True, help_text="MM/YY")
    cvv = models.CharField(max_length=4, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Card'
        verbose_name_plural = 'Cards'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.card_brand} {self.masked_number}"

    def save(self, *args, **kwargs):
        if not self.card_number:
            prefix = '4' if self.card_brand.lower() == 'visa' else '5'
            self.card_number = prefix + ''.join(str(random.randint(0, 9)) for _ in range(15))
        if not self.expiry:
            now = timezone.now()
            self.expiry = f"{now.month:02d}/{(now.year + 4) % 100:02d}"
        if not self.cvv:
            self.cvv = ''.join(str(random.randint(0, 9)) for _ in range(3))
        super().save(*args, **kwargs)

    @property
    def masked_number(self):
        if not self.card_number or len(self.card_number) < 4:
            return '•••• •••• •••• ••••'
        return f"•••• •••• •••• {self.card_number[-4:]}"
