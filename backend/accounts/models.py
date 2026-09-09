from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from datetime import timedelta
import secrets
import string
import uuid


class User(AbstractUser):
    """
    Custom User model extending Django's AbstractUser
    Adds investment-related fields for the platform
    """
    # Contact Information
    phone = models.CharField(max_length=20, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)

    # Profile
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)

    # Financial Fields
    balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00,
        help_text="User's available balance"
    )
    total_profit = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00,
        help_text="Total profit earned from investments"
    )
    total_bonus = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00,
        help_text="Total bonuses received"
    )
    referral_bonus = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00,
        help_text="Total earnings from referrals"
    )
    btc_balance = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        default=0,
        help_text="User's BTC balance (from USD<->BTC swaps)"
    )

    # Referral System
    referral_code = models.CharField(
        max_length=10,
        unique=True,
        blank=True,
        help_text="Unique referral code for this user"
    )
    referred_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='referrals',
        help_text="User who referred this user"
    )

    # Account Status
    transfers_blocked = models.BooleanField(
        default=False,
        help_text="Block this customer from sending money. They keep full read access "
                  "and are told to contact support.",
    )
    is_verified = models.BooleanField(
        default=False,
        help_text="Email verification status"
    )

    # Security
    withdrawal_otp = models.CharField(max_length=6, blank=True, null=True)
    transaction_pin = models.CharField(
        max_length=128, blank=True,
        help_text="Hashed transaction PIN for authorising transfers"
    )

    # Bank Details
    bank_name = models.CharField(max_length=200, blank=True)
    account_name = models.CharField(max_length=200, blank=True)
    account_number = models.CharField(max_length=100, blank=True)
    swift_code = models.CharField(max_length=50, blank=True)

    # Cryptocurrency Addresses
    btc_address = models.CharField(max_length=200, blank=True, verbose_name="Bitcoin Address")
    eth_address = models.CharField(max_length=200, blank=True, verbose_name="Ethereum Address")
    ltc_address = models.CharField(max_length=200, blank=True, verbose_name="Litecoin Address")
    usdt_address = models.CharField(max_length=200, blank=True, verbose_name="USDT Address")

    # Email Notification Preferences
    email_on_withdrawal = models.BooleanField(default=True, help_text="Receive email on withdrawal requests")
    email_on_roi = models.BooleanField(default=True, help_text="Receive email on ROI/profit credits")
    email_on_expiration = models.BooleanField(default=True, help_text="Receive email on plan expiration")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-created_at']

    def __str__(self):
        return self.username

    def save(self, *args, **kwargs):
        # Generate referral code if not exists
        if not self.referral_code:
            self.referral_code = self.generate_referral_code()
        super().save(*args, **kwargs)

    def generate_referral_code(self):
        """Generate a unique 8-character referral code"""
        while True:
            code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
            if not User.objects.filter(referral_code=code).exists():
                return code

    @property
    def total_deposited(self):
        """Calculate total amount deposited by user"""
        from transactions.models import Transaction
        return Transaction.objects.filter(
            user=self,
            type='deposit',
            status='approved'
        ).aggregate(models.Sum('amount'))['amount__sum'] or 0

    @property
    def total_withdrawn(self):
        """Calculate total amount withdrawn by user"""
        from transactions.models import Transaction
        return Transaction.objects.filter(
            user=self,
            type='withdrawal',
            status='approved'
        ).aggregate(models.Sum('amount'))['amount__sum'] or 0

    # Money in / out for the current calendar month.
    #
    # The type split mirrors Transaction.approve() exactly, which is the
    # ledger's own definition of what moves a balance. 'swap' is excluded
    # from both sides because it is balance-neutral (USD out, BTC in).
    INCOME_TYPES = ('deposit', 'bonus', 'referral', 'profit', 'loan', 'grant')
    EXPENSE_TYPES = ('withdrawal',)

    def _month_total(self, types, include_held=False):
        from django.db.models import Q
        from django.utils import timezone
        from transactions.models import Transaction
        now = timezone.now()

        # Money that has actually moved against the balance this month.
        # Approved always counts. Pending money OUT counts too when the funds
        # were held at submission, because the balance already reflects it —
        # without this the customer sees their balance drop while "Out" stays
        # put, and the two figures cannot be reconciled.
        settled = Q(status='approved')
        if include_held:
            settled |= Q(status='pending', funds_held=True)

        return Transaction.objects.filter(
            settled, user=self, type__in=types,
            created_at__year=now.year, created_at__month=now.month,
        ).aggregate(models.Sum('amount'))['amount__sum'] or 0

    @property
    def income_this_month(self):
        """Approved money in this calendar month.

        Pending deposits are excluded: nothing has been credited yet.

        Note: user-to-user Transfers write no Transaction row, so internal
        transfers received are not counted here. The dashboard labels this
        as deposits and credits rather than claiming to be a full statement.
        """
        return self._month_total(self.INCOME_TYPES)

    @property
    def expense_this_month(self):
        """Money out this calendar month, including transfers still in review.

        A pending transfer has already been debited, so it belongs here — this
        is what makes Out agree with the balance on screen.
        """
        return self._month_total(self.EXPENSE_TYPES, include_held=True)

    @property
    def referral_count(self):
        """Count number of users referred by this user"""
        return self.referrals.count()

    def get_full_name(self):
        """Return user's full name or username"""
        full_name = super().get_full_name()
        return full_name if full_name else self.username

    # ---- Transaction PIN (hashed; never stored in plaintext) ----
    def set_transaction_pin(self, raw_pin):
        from django.contrib.auth.hashers import make_password
        self.transaction_pin = make_password(str(raw_pin))

    def check_transaction_pin(self, raw_pin):
        from django.contrib.auth.hashers import check_password
        if not self.transaction_pin:
            return False
        return check_password(str(raw_pin), self.transaction_pin)

    @property
    def has_transaction_pin(self):
        return bool(self.transaction_pin)


class PasswordResetToken(models.Model):
    """Model for password reset tokens"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='password_reset_tokens')
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Password Reset Token'
        verbose_name_plural = 'Password Reset Tokens'
        ordering = ['-created_at']

    def __str__(self):
        return f"Password reset token for {self.user.username}"

    def save(self, *args, **kwargs):
        if not self.expires_at:
            # Token expires in 1 hour
            self.expires_at = timezone.now() + timedelta(hours=1)
        super().save(*args, **kwargs)

    def is_valid(self):
        """Check if token is still valid"""
        return not self.is_used and timezone.now() < self.expires_at

    def mark_as_used(self):
        """Mark token as used"""
        self.is_used = True
        self.save()


class LoginHistory(models.Model):
    """Model to track user login history"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='login_history')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    location = models.CharField(max_length=255, blank=True)
    login_time = models.DateTimeField(auto_now_add=True)
    success = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Login History'
        verbose_name_plural = 'Login History'
        ordering = ['-login_time']

    def __str__(self):
        return f"{self.user.username} - {self.login_time.strftime('%Y-%m-%d %H:%M:%S')}"


class Notification(models.Model):
    """Model for user notifications"""
    TYPE_CHOICES = [
        ('deposit', 'Deposit'),
        ('withdrawal', 'Withdrawal'),
        ('investment', 'Investment'),
        ('profit', 'Profit'),
        ('bonus', 'Bonus'),
        ('referral', 'Referral'),
        ('system', 'System'),
        ('security', 'Security'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200)
    message = models.TextField()
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='system')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.title}"

    def mark_as_read(self):
        """Mark notification as read"""
        self.is_read = True
        self.save()


class EmailOTP(models.Model):
    """Six-digit one-time code, emailed to the user.

    Replaces the click-through EmailVerificationToken for signup, and backs the
    withdrawal authorisation that previously generated a code but never sent it.
    """

    PURPOSE_CHOICES = [
        ('signup', 'Signup verification'),
        ('withdrawal', 'Withdrawal authorisation'),
    ]

    MAX_ATTEMPTS = 5
    TTL_MINUTES = 10

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='otps')
    code = models.CharField(max_length=6)
    purpose = models.CharField(max_length=20, choices=PURPOSE_CHOICES, default='signup')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    is_used = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Email OTP'
        verbose_name_plural = 'Email OTPs'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['user', 'purpose', 'is_used'])]

    def __str__(self):
        return f"{self.get_purpose_display()} for {self.user.username}"

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=self.TTL_MINUTES)
        super().save(*args, **kwargs)

    @classmethod
    def issue(cls, user, purpose='signup'):
        """Invalidate any outstanding code for this purpose, then mint a new one."""
        cls.objects.filter(user=user, purpose=purpose, is_used=False).update(is_used=True)
        code = ''.join(secrets.choice(string.digits) for _ in range(6))
        return cls.objects.create(user=user, code=code, purpose=purpose)

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    def is_valid(self):
        return (not self.is_used
                and not self.is_expired
                and self.attempts < self.MAX_ATTEMPTS)

    def verify(self, submitted):
        """Return (ok, reason). Counts the attempt either way."""
        if self.is_used:
            return False, 'This code has already been used.'
        if self.is_expired:
            return False, 'This code has expired. Request a new one.'
        if self.attempts >= self.MAX_ATTEMPTS:
            return False, 'Too many incorrect attempts. Request a new code.'

        self.attempts += 1
        if secrets.compare_digest(str(submitted).strip(), self.code):
            self.is_used = True
            self.save(update_fields=['attempts', 'is_used'])
            return True, ''
        self.save(update_fields=['attempts'])
        remaining = self.MAX_ATTEMPTS - self.attempts
        if remaining <= 0:
            return False, 'Too many incorrect attempts. Request a new code.'
        return False, f'That code is not correct. {remaining} attempt(s) remaining.'


class KYCProfile(models.Model):
    """Stage-two identity details, collected after signup rather than at the gate.

    Registration asks only for what is needed to create an account; everything a
    bank actually has to verify lives here and is completed from the dashboard.
    """

    STATUS_CHOICES = [
        ('incomplete', 'Not submitted'),
        ('pending', 'Pending review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    GENDER_CHOICES = [('male', 'Male'), ('female', 'Female'), ('other', 'Other')]
    EMPLOYMENT_CHOICES = [
        ('employed', 'Employed'), ('self_employed', 'Self-employed'),
        ('unemployed', 'Unemployed'), ('retired', 'Retired'), ('student', 'Student'),
    ]
    ID_TYPE_CHOICES = [
        ('passport', 'Passport'), ('drivers_license', "Driver's licence"),
        ('national_id', 'National ID'), ('state_id', 'State ID'),
    ]
    TAX_ID_TYPE_CHOICES = [('ssn', 'SSN'), ('itin', 'ITIN'), ('ein', 'EIN'), ('other', 'Other')]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='kyc')

    # Personal
    middle_name = models.CharField(max_length=100, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)
    country_of_citizenship = models.CharField(max_length=100, blank=True)
    citizenship_status = models.CharField(max_length=100, blank=True)

    # Tax
    tax_id_type = models.CharField(max_length=10, choices=TAX_ID_TYPE_CHOICES, blank=True)
    tax_id = models.CharField(max_length=20, blank=True)

    # Address
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    zipcode = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, blank=True)

    # Employment
    employment_status = models.CharField(max_length=20, choices=EMPLOYMENT_CHOICES, blank=True)
    employer = models.CharField(max_length=150, blank=True)
    job_title = models.CharField(max_length=150, blank=True)
    years_employed = models.CharField(max_length=20, blank=True)
    employer_phone = models.CharField(max_length=30, blank=True)
    annual_income = models.CharField(max_length=50, blank=True)
    source_of_income = models.CharField(max_length=100, blank=True)

    # Identity document
    id_type = models.CharField(max_length=20, choices=ID_TYPE_CHOICES, blank=True)
    id_number = models.CharField(max_length=60, blank=True)
    id_state = models.CharField(max_length=100, blank=True)
    id_issue_date = models.DateField(null=True, blank=True)
    id_expiry_date = models.DateField(null=True, blank=True)
    id_document = models.FileField(upload_to='kyc/', blank=True, null=True)

    # Security question
    security_question = models.CharField(max_length=200, blank=True)
    security_answer = models.CharField(max_length=200, blank=True)

    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='incomplete')
    admin_note = models.TextField(blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'KYC Profile'
        verbose_name_plural = 'KYC Profiles'

    def __str__(self):
        return f"KYC for {self.user.username} ({self.get_status_display()})"

    REQUIRED_FIELDS_FOR_SUBMISSION = (
        'date_of_birth', 'address', 'city', 'country',
        'tax_id', 'id_type', 'id_number',
    )

    @property
    def missing_fields(self):
        return [f for f in self.REQUIRED_FIELDS_FOR_SUBMISSION if not getattr(self, f)]

    @property
    def is_complete(self):
        return not self.missing_fields and bool(self.id_document)
