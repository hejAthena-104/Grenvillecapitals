from django.db import models
from django.utils import timezone
from accounts.models import User


class Transaction(models.Model):
    """Model for all user transactions (deposits, withdrawals, transfers)"""

    TYPE_CHOICES = [
        ('deposit', 'Deposit'),
        ('withdrawal', 'Withdrawal'),
        ('transfer', 'Transfer'),
        ('bonus', 'Bonus'),
        ('referral', 'Referral Bonus'),
        ('loan', 'Loan Disbursement'),
        ('grant', 'Grant Disbursement'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ]

    PAYMENT_METHOD_CHOICES = [
        ('bank_transfer', 'Bank Transfer'),
        ('paypal', 'PayPal'),
        ('stripe', 'Credit/Debit Card'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions')

    # Transaction details
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Payment details
    payment_method = models.CharField(max_length=50, choices=PAYMENT_METHOD_CHOICES, null=True, blank=True)
    payment_reference = models.CharField(max_length=255, blank=True, help_text="Transaction ID or reference")
    payment_address = models.CharField(max_length=255, blank=True, help_text="Bank account details")

    # Additional info
    description = models.TextField(blank=True)
    admin_note = models.TextField(blank=True, help_text="Internal notes for administrators")

    # For transfers
    funds_held = models.BooleanField(
        default=False,
        help_text='Money already debited when the request was submitted, so approving must not debit again.',
    )
    recipient = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='received_transfers')

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Transaction'
        verbose_name_plural = 'Transactions'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.type} - ${self.amount} - {self.status}"

    def approve(self):
        """Approve transaction and update user balance"""
        if self.status != 'pending':
            return False

        self.status = 'approved'
        self.processed_at = timezone.now()

        # Update user balance based on transaction type
        if self.type == 'deposit':
            self.user.balance += self.amount
        elif self.type == 'withdrawal':
            # Money out is debited when the customer submits, so the balance
            # they see already reflects it. Approving must not debit twice.
            if not self.funds_held:
                if self.user.balance >= self.amount:
                    self.user.balance -= self.amount
                else:
                    return False  # Insufficient balance
        elif self.type in ['bonus', 'referral', 'loan', 'grant']:
            self.user.balance += self.amount

        self.user.save()
        self.save()
        return True

    def reject(self, reason=''):
        """Reject the transaction, returning any money that was held for it."""
        if self.status != 'pending':
            return False
        if self.funds_held:
            self.user.balance += self.amount
            self.user.save(update_fields=['balance'])
            self.funds_held = False
        self.status = 'rejected'
        self.admin_note = reason
        self.processed_at = timezone.now()
        self.save()
        return True


class Deposit(models.Model):
    """Model for deposit requests (extends Transaction)"""

    transaction = models.OneToOneField(Transaction, on_delete=models.CASCADE, related_name='deposit_details')

    # Proof of payment
    proof_image = models.ImageField(upload_to='deposits/', null=True, blank=True)

    class Meta:
        verbose_name = 'Deposit'
        verbose_name_plural = 'Deposits'
        ordering = ['-transaction__created_at']

    def __str__(self):
        return f"Deposit - {self.transaction}"


class Withdrawal(models.Model):
    """Model for withdrawal requests (extends Transaction)"""

    transaction = models.OneToOneField(Transaction, on_delete=models.CASCADE, related_name='withdrawal_details')

    # Withdrawal details
    withdrawal_address = models.CharField(max_length=255, help_text="Wallet address or account details")
    withdrawal_method = models.CharField(max_length=50)

    class Meta:
        verbose_name = 'Withdrawal'
        verbose_name_plural = 'Withdrawals'
        ordering = ['-transaction__created_at']

    def __str__(self):
        return f"Withdrawal - {self.transaction}"


class Transfer(models.Model):
    """Model for internal fund transfers between users"""

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transfers_sent')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transfers_received')

    amount = models.DecimalField(max_digits=15, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    description = models.TextField(blank=True)

    # Fees
    fee_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    total_deducted = models.DecimalField(max_digits=15, decimal_places=2, help_text="Amount + Fee")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Transfer'
        verbose_name_plural = 'Transfers'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.sender.username} → {self.recipient.username} - ${self.amount}"

    def save(self, *args, **kwargs):
        # Calculate total deducted (amount + fee)
        if not self.total_deducted or self.total_deducted == 0:
            self.total_deducted = self.amount + self.fee_amount
        super().save(*args, **kwargs)

    def complete(self):
        """Complete the transfer - deduct from sender and credit recipient"""
        if self.status != 'pending':
            return False

        # Check if sender has sufficient balance
        if self.sender.balance < self.total_deducted:
            self.status = 'failed'
            self.save()
            return False

        # Deduct from sender
        self.sender.balance -= self.total_deducted
        self.sender.save()

        # Credit recipient
        self.recipient.balance += self.amount
        self.recipient.save()

        # Update status
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save()

        return True

    def cancel(self):
        """Cancel the transfer"""
        if self.status == 'pending':
            self.status = 'cancelled'
            self.save()
            return True
        return False


class PaymentMethod(models.Model):
    """Payment methods (deposit & withdrawal). Relocated from the removed investments app."""

    TYPE_CHOICES = [
        ('deposit', 'Deposit Only'),
        ('withdrawal', 'Withdrawal Only'),
        ('both', 'Both'),
    ]

    CHARGE_TYPE_CHOICES = [
        ('fixed', 'Fixed Amount'),
        ('percentage', 'Percentage'),
    ]

    name = models.CharField(max_length=50, unique=True, help_text="e.g., Bank Transfer")
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='both')
    icon = models.ImageField(upload_to='payment_methods/', blank=True, null=True)

    min_amount = models.DecimalField(max_digits=15, decimal_places=2, default=10.00)
    max_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, help_text="Leave blank for no limit")

    charge_type = models.CharField(max_length=20, choices=CHARGE_TYPE_CHOICES, default='percentage')
    charge_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Amount or percentage based on charge type")

    duration = models.CharField(max_length=100, blank=True, help_text="e.g., '1-24 hours', 'Instant'")

    is_active = models.BooleanField(default=True)
    order = models.IntegerField(default=0, help_text="Display order")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Payment Method'
        verbose_name_plural = 'Payment Methods'
        ordering = ['order', 'name']

    def __str__(self):
        return f"{self.name} ({self.get_type_display()})"

    def calculate_charge(self, amount):
        if self.charge_type == 'fixed':
            return self.charge_amount
        return (amount * self.charge_amount) / 100

    def get_total_amount(self, base_amount):
        return base_amount + self.calculate_charge(base_amount)


class Beneficiary(models.Model):
    """Saved transfer recipient (bank / wire / wallet service)."""
    TYPE_CHOICES = [
        ('local_bank', 'Local Bank'),
        ('wire', 'International Wire'),
        ('paypal', 'PayPal'),
        ('wise', 'Wise'),
        ('cashapp', 'Cash App'),
        ('other', 'Other'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='beneficiaries')
    nickname = models.CharField(max_length=100, help_text="Label for this beneficiary")
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='local_bank')

    account_holder_name = models.CharField(max_length=150, blank=True)
    account_number = models.CharField(max_length=100, blank=True)
    bank_name = models.CharField(max_length=150, blank=True)
    account_type = models.CharField(max_length=50, blank=True)
    routing_number = models.CharField(max_length=50, blank=True)
    swift_code = models.CharField(max_length=50, blank=True)
    country = models.CharField(max_length=100, blank=True)
    extra = models.JSONField(default=dict, blank=True, help_text="Method-specific details (email, tag, etc.)")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Beneficiary'
        verbose_name_plural = 'Beneficiaries'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.nickname} ({self.get_type_display()})"


class ExternalTransfer(models.Model):
    """Local / International outbound transfer detail. OneToOne to a pending withdrawal
    Transaction so it reuses Transaction.approve() to debit balance on admin approval."""
    TRANSFER_TYPE_CHOICES = [
        ('local', 'Local Transfer'),
        ('international', 'International Transfer'),
    ]
    METHOD_CHOICES = [
        ('local_bank', 'Local Bank'),
        ('wire', 'Wire Transfer'),
        ('paypal', 'PayPal'),
        ('wise', 'Wise'),
        ('cashapp', 'Cash App'),
        ('other', 'Other'),
    ]

    transaction = models.OneToOneField(Transaction, on_delete=models.CASCADE, related_name='external_transfer')
    beneficiary = models.ForeignKey(Beneficiary, on_delete=models.SET_NULL, null=True, blank=True, related_name='transfers')

    transfer_type = models.CharField(max_length=20, choices=TRANSFER_TYPE_CHOICES)
    method = models.CharField(max_length=20, choices=METHOD_CHOICES, default='local_bank')
    fee = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)

    # Snapshot of recipient details at submission time
    account_holder_name = models.CharField(max_length=150, blank=True)
    account_number = models.CharField(max_length=100, blank=True)
    bank_name = models.CharField(max_length=150, blank=True)
    account_type = models.CharField(max_length=50, blank=True)
    routing_number = models.CharField(max_length=50, blank=True)
    swift_code = models.CharField(max_length=50, blank=True)
    country = models.CharField(max_length=100, blank=True)
    extra = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = 'External Transfer'
        verbose_name_plural = 'External Transfers'
        ordering = ['-transaction__created_at']

    def __str__(self):
        return f"{self.get_transfer_type_display()} - {self.transaction}"


class FeatureFlags(models.Model):
    """Singleton switchboard for optional features.

    The flag hides a feature from the navigation and the dashboard and closes
    its view, so turning it off leaves no dangling links.
    """

    loans_enabled = models.BooleanField(default=True, help_text='Show loan applications.')
    grants_enabled = models.BooleanField(default=True, help_text='Show grant applications.')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Feature Flags'
        verbose_name_plural = 'Feature Flags'

    def __str__(self):
        return 'Feature flags'

    def save(self, *args, **kwargs):
        self.pk = 1          # singleton
        super().save(*args, **kwargs)

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
