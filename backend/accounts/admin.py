from django.utils.html import format_html
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group
from .models import EmailOTP, KYCProfile, User, LoginHistory, Notification

# Remove the default Django "Groups" model from the admin — this platform does not
# use group-based permissions, so it is just clutter.
try:
    admin.site.unregister(Group)
except admin.sites.NotRegistered:
    pass


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin interface for custom User model"""

    # Fields to display in the user list
    list_display = (
        'username',
        'email',
        'first_name',
        'last_name',
        'balance',
        'total_profit',
        'referral_code',
        'is_verified',
        'is_staff',
        'is_active',
        'created_at'
    )

    # Fields to filter by
    list_filter = (
        'is_staff',
        'is_active',
        'is_verified',
        'created_at',
        'date_joined'
    )

    # Fields to search
    search_fields = (
        'username',
        'email',
        'first_name',
        'last_name',
        'phone',
        'referral_code'
    )

    # Read-only fields
    readonly_fields = (
        'referral_code',
        'created_at',
        'updated_at',
        'date_joined',
        'last_login'
    )

    # Fieldsets for the user detail page
    fieldsets = (
        (None, {
            'fields': ('username', 'password')
        }),
        ('Personal Info', {
            'fields': ('first_name', 'last_name', 'email', 'phone')
        }),
        ('Financial Information', {
            'fields': (
                'balance',
                'total_profit',
                'total_bonus',
                'referral_bonus'
            )
        }),
        ('Referral Information', {
            'fields': ('referral_code', 'referred_by')
        }),
        ('Permissions', {
            'fields': (
                'is_active',
                'is_verified',
                'is_staff',
                'is_superuser',
                'groups',
                'user_permissions'
            )
        }),
        ('Important Dates', {
            'fields': ('last_login', 'date_joined', 'created_at', 'updated_at')
        }),
    )

    # Fieldsets for adding a new user
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'username',
                'email',
                'password1',
                'password2',
                'first_name',
                'last_name',
                'phone',
                'is_staff',
                'is_active'
            ),
        }),
    )

    # Order by newest first
    ordering = ('-created_at',)


# EmailVerificationToken and PasswordResetToken are transient internal plumbing
# (auto-created and consumed during signup / password reset). They are intentionally
# NOT registered in the admin to keep it focused on platform management.


@admin.register(LoginHistory)
class LoginHistoryAdmin(admin.ModelAdmin):
    """Admin interface for Login History"""
    list_display = ('user', 'ip_address', 'login_time', 'success')
    list_filter = ('success', 'login_time')
    search_fields = ('user__username', 'user__email', 'ip_address')
    readonly_fields = ('user', 'ip_address', 'user_agent', 'location', 'login_time', 'success')
    ordering = ('-login_time',)

    def has_add_permission(self, request):
        return False


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """Admin interface for Notifications"""
    list_display = ('user', 'title', 'type', 'is_read', 'created_at')
    list_filter = ('type', 'is_read', 'created_at')
    search_fields = ('user__username', 'user__email', 'title', 'message')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)

    actions = ['mark_as_read', 'mark_as_unread']

    def mark_as_read(self, request, queryset):
        queryset.update(is_read=True)
        self.message_user(request, f"{queryset.count()} notification(s) marked as read.")
    mark_as_read.short_description = "Mark selected notifications as read"

    def mark_as_unread(self, request, queryset):
        queryset.update(is_read=False)
        self.message_user(request, f"{queryset.count()} notification(s) marked as unread.")
    mark_as_unread.short_description = "Mark selected notifications as unread"


@admin.register(EmailOTP)
class EmailOTPAdmin(admin.ModelAdmin):
    list_display = ('user', 'purpose', 'is_used', 'attempts', 'created_at', 'expires_at')
    list_filter = ('purpose', 'is_used', 'created_at')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('code', 'created_at', 'expires_at', 'attempts')


@admin.register(KYCProfile)
class KYCProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'status', 'id_type', 'submitted_at', 'updated_at')
    list_filter = ('status', 'id_type', 'employment_status')
    search_fields = ('user__username', 'user__email', 'id_number', 'tax_id')
    readonly_fields = ('created_at', 'updated_at', 'submitted_at', 'id_document_preview')
    fieldsets = (
        ('Account', {'fields': ('user', 'status', 'admin_note')}),
        ('Personal', {'fields': ('middle_name', 'date_of_birth', 'gender',
                                 'country_of_citizenship', 'citizenship_status')}),
        ('Tax', {'fields': ('tax_id_type', 'tax_id')}),
        ('Address', {'fields': ('address', 'city', 'state', 'zipcode', 'country')}),
        ('Employment', {'fields': ('employment_status', 'employer', 'job_title',
                                   'years_employed', 'employer_phone', 'annual_income',
                                   'source_of_income')}),
        ('Identity document', {'fields': ('id_type', 'id_number', 'id_state',
                                          'id_issue_date', 'id_expiry_date',
                                          'id_document', 'id_document_preview')}),
        ('Security question', {'fields': ('security_question', 'security_answer')}),
        ('Timestamps', {'fields': ('submitted_at', 'processed_at', 'created_at', 'updated_at')}),
    )

    @admin.display(description='Uploaded document')
    def id_document_preview(self, obj):
        if not obj.id_document:
            return 'No document uploaded'
        return format_html('<a href="{}" target="_blank" rel="noopener">Open document</a>',
                           obj.id_document.url)
