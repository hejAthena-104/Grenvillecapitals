from django.contrib import admin
from .models import SupportTicket, EmailLog


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = ['recipient', 'subject', 'template', 'sent', 'sent_by', 'created_at']
    list_filter = ['sent', 'template', 'created_at']
    search_fields = ['recipient', 'recipient_name', 'subject', 'content']
    readonly_fields = ['created_at']

    fieldsets = (
        ('Email Information', {
            'fields': ('recipient', 'recipient_name', 'subject', 'template')
        }),
        ('Content', {
            'fields': ('content',)
        }),
        ('Status', {
            'fields': ('sent', 'error_message', 'sent_by')
        }),
        ('Timestamp', {
            'fields': ('created_at',)
        }),
    )


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ['ticket_number', 'user', 'subject', 'category', 'status', 'priority', 'created_at']
    list_filter = ['status', 'priority', 'category', 'created_at']
    search_fields = ['ticket_number', 'user__username', 'user__email', 'subject', 'message']
    readonly_fields = ['ticket_number', 'created_at', 'updated_at']

    fieldsets = (
        ('Ticket Information', {
            'fields': ('ticket_number', 'user', 'subject', 'category', 'message')
        }),
        ('Status', {
            'fields': ('status', 'priority')
        }),
        ('Admin Response', {
            'fields': ('admin_response', 'responded_at', 'resolved_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )

    actions = ['mark_as_resolved', 'mark_as_closed']

    def mark_as_resolved(self, request, queryset):
        queryset.update(status='resolved')
        self.message_user(request, f"{queryset.count()} ticket(s) marked as resolved.")
    mark_as_resolved.short_description = "Mark selected tickets as resolved"

    def mark_as_closed(self, request, queryset):
        for ticket in queryset:
            ticket.close()
        self.message_user(request, f"{queryset.count()} ticket(s) closed.")
    mark_as_closed.short_description = "Close selected tickets"
