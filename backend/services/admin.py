from django.contrib import admin
from django.utils.html import format_html
from .models import LoanApplication, GrantApplication, CardApplication, Card


def _badge(status):
    colors = {'pending': 'orange', 'approved': 'green', 'active': 'green',
              'rejected': 'red', 'frozen': 'blue', 'blocked': 'red'}
    return format_html(
        '<span style="background-color:{}; color:white; padding:3px 10px; border-radius:3px; font-weight:bold;">{}</span>',
        colors.get(status, 'gray'), str(status).upper())


class _ReviewAdmin(admin.ModelAdmin):
    """Shared admin with approve/reject bulk actions for review-gated applications."""
    actions = ['approve_selected', 'reject_selected']
    readonly_fields = ('created_at', 'processed_at')

    def status_badge(self, obj):
        return _badge(obj.status)
    status_badge.short_description = 'Status'

    def approve_selected(self, request, queryset):
        n = sum(1 for o in queryset.filter(status='pending') if o.approve())
        self.message_user(request, f'{n} application(s) approved.')
    approve_selected.short_description = 'Approve selected'

    def reject_selected(self, request, queryset):
        n = 0
        for o in queryset.filter(status='pending'):
            o.reject('Rejected by admin')
            n += 1
        self.message_user(request, f'{n} application(s) rejected.')
    reject_selected.short_description = 'Reject selected'


@admin.register(LoanApplication)
class LoanApplicationAdmin(_ReviewAdmin):
    list_display = ('id', 'user', 'amount', 'purpose', 'term_months', 'status_badge', 'created_at')
    list_filter = ('status', 'purpose', 'created_at')
    search_fields = ('user__username', 'user__email')


@admin.register(GrantApplication)
class GrantApplicationAdmin(_ReviewAdmin):
    list_display = ('id', 'user', 'applicant_type', 'amount', 'purpose', 'status_badge', 'created_at')
    list_filter = ('status', 'applicant_type', 'created_at')
    search_fields = ('user__username', 'user__email', 'business_name', 'full_name')


@admin.register(CardApplication)
class CardApplicationAdmin(_ReviewAdmin):
    list_display = ('id', 'user', 'card_type', 'card_brand', 'status_badge', 'created_at')
    list_filter = ('status', 'card_type', 'card_brand', 'created_at')
    search_fields = ('user__username', 'user__email', 'full_name')


@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'card_brand', 'masked_number', 'card_type', 'status', 'balance', 'created_at')
    list_filter = ('status', 'card_type', 'card_brand')
    list_editable = ('status', 'balance')
    search_fields = ('user__username', 'user__email', 'card_holder')
    readonly_fields = ('card_number', 'cvv', 'expiry', 'created_at')
