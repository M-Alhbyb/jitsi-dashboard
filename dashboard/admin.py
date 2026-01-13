from django.contrib import admin
from django.utils.html import format_html
from .models import (
    JitsiServer, Conference, Participant, 
    Recording, WebhookEvent, DashboardSettings
)


@admin.register(JitsiServer)
class JitsiServerAdmin(admin.ModelAdmin):
    list_display = ['name', 'base_url', 'is_active', 'is_primary', 'updated_at']
    list_filter = ['is_active', 'is_primary']
    search_fields = ['name', 'base_url']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Server Information', {
            'fields': ('name', 'base_url', 'is_active', 'is_primary')
        }),
        ('Ports', {
            'fields': ('colibri_port', 'jicofo_port', 'jibri_port'),
            'classes': ('collapse',)
        }),
        ('Authentication', {
            'fields': ('app_id', 'app_secret', 'verify_ssl'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Conference)
class ConferenceAdmin(admin.ModelAdmin):
    list_display = ['room_name', 'display_name', 'status', 'server', 
                   'max_participants', 'duration_display', 'started_at']
    list_filter = ['status', 'server', 'is_recorded', 'is_password_protected']
    search_fields = ['room_name', 'display_name']
    readonly_fields = ['created_at', 'duration_display']
    date_hierarchy = 'started_at'
    
    def duration_display(self, obj):
        mins = obj.duration
        if mins >= 60:
            hours = mins // 60
            mins = mins % 60
            return f"{hours}h {mins}m"
        return f"{mins}m"
    duration_display.short_description = "Duration"


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ['name', 'conference', 'is_moderator', 'joined_at', 
                   'left_at', 'duration_minutes']
    list_filter = ['is_moderator', 'conference__server']
    search_fields = ['name', 'email', 'conference__room_name']
    date_hierarchy = 'joined_at'


@admin.register(Recording)
class RecordingAdmin(admin.ModelAdmin):
    list_display = ['conference', 'recording_type', 'status', 
                   'file_size_mb', 'started_at']
    list_filter = ['recording_type', 'status']
    search_fields = ['conference__room_name', 'session_id']
    readonly_fields = ['created_at']


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ['event_type', 'room_name', 'processed', 'received_at']
    list_filter = ['event_type', 'processed', 'server']
    search_fields = ['room_name']
    readonly_fields = ['payload', 'received_at']
    date_hierarchy = 'received_at'


@admin.register(DashboardSettings)
class DashboardSettingsAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'refresh_interval_seconds', 'dark_mode', 'updated_at']
    fieldsets = (
        ('General', {
            'fields': ('refresh_interval_seconds', 'default_jwt_expiry_hours', 
                      'max_recent_conferences')
        }),
        ('Webhooks', {
            'fields': ('enable_webhooks', 'webhook_secret')
        }),
        ('UI Preferences', {
            'fields': ('dark_mode', 'show_bandwidth_graphs')
        }),
        ('Notifications', {
            'fields': ('notify_on_new_conference', 'notify_on_high_load', 
                      'high_load_threshold')
        }),
    )
    
    def has_add_permission(self, request):
        # Singleton - only allow one instance
        return not DashboardSettings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        return False
