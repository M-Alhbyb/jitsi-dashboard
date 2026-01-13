from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class JitsiServer(models.Model):
    """
    Model representing a Jitsi server configuration.
    Supports multiple servers for scalability.
    """
    name = models.CharField(max_length=100, unique=True)
    base_url = models.URLField(help_text="e.g., https://192.168.117.153")
    colibri_port = models.IntegerField(default=8080)
    jicofo_port = models.IntegerField(default=8888)
    jibri_port = models.IntegerField(default=2222)
    app_id = models.CharField(max_length=100, default="jitsi_dashboard")
    app_secret = models.CharField(max_length=255, blank=True, 
                                   help_text="Secret key for JWT tokens")
    is_active = models.BooleanField(default=True)
    is_primary = models.BooleanField(default=False, 
                                      help_text="Primary server for new meetings")
    verify_ssl = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-is_primary', 'name']
        verbose_name = "Jitsi Server"
        verbose_name_plural = "Jitsi Servers"
    
    def __str__(self):
        return f"{self.name} ({self.base_url})"
    
    def save(self, *args, **kwargs):
        # Ensure only one primary server
        if self.is_primary:
            JitsiServer.objects.filter(is_primary=True).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)


class Conference(models.Model):
    """
    Model to track conference/meeting history.
    Data populated via webhooks or polling.
    """
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('ended', 'Ended'),
        ('scheduled', 'Scheduled'),
    ]
    
    server = models.ForeignKey(JitsiServer, on_delete=models.CASCADE, 
                                related_name='conferences')
    room_name = models.CharField(max_length=255, db_index=True)
    display_name = models.CharField(max_length=255, blank=True,
                                     help_text="Human-friendly meeting name")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # JWT-generated meeting info
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, 
                                    null=True, blank=True,
                                    related_name='created_conferences')
    is_password_protected = models.BooleanField(default=False)
    has_lobby = models.BooleanField(default=False)
    
    # Statistics
    max_participants = models.IntegerField(default=0)
    total_participants = models.IntegerField(default=0)
    
    # Timestamps
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Recording info
    is_recorded = models.BooleanField(default=False)
    recording_url = models.URLField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Conference"
        verbose_name_plural = "Conferences"
        indexes = [
            models.Index(fields=['room_name', 'server']),
            models.Index(fields=['status']),
            models.Index(fields=['started_at']),
        ]
    
    def __str__(self):
        return f"{self.display_name or self.room_name} ({self.status})"
    
    @property
    def duration(self):
        """Calculate meeting duration in minutes."""
        if self.started_at and self.ended_at:
            delta = self.ended_at - self.started_at
            return int(delta.total_seconds() / 60)
        elif self.started_at and self.status == 'active':
            delta = timezone.now() - self.started_at
            return int(delta.total_seconds() / 60)
        return 0
    
    @property
    def meeting_url(self):
        """Generate the meeting URL."""
        return f"{self.server.base_url}/{self.room_name}"


class Participant(models.Model):
    """
    Model to track participant history in conferences.
    """
    conference = models.ForeignKey(Conference, on_delete=models.CASCADE,
                                    related_name='participants')
    participant_id = models.CharField(max_length=100, blank=True,
                                       help_text="Jitsi internal participant ID")
    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True)
    is_moderator = models.BooleanField(default=False)
    
    joined_at = models.DateTimeField(default=timezone.now)
    left_at = models.DateTimeField(null=True, blank=True)
    disconnect_reason = models.CharField(max_length=50, blank=True,
                                          help_text="Why participant left")
    
    # User association (if authenticated)
    user = models.ForeignKey(User, on_delete=models.SET_NULL,
                              null=True, blank=True,
                              related_name='participations')
    
    class Meta:
        ordering = ['-joined_at']
        verbose_name = "Participant"
        verbose_name_plural = "Participants"
    
    def __str__(self):
        return f"{self.name} in {self.conference.room_name}"
    
    @property
    def duration_minutes(self):
        """Calculate participant's time in meeting."""
        end_time = self.left_at or timezone.now()
        if self.joined_at:
            delta = end_time - self.joined_at
            return int(delta.total_seconds() / 60)
        return 0


class Recording(models.Model):
    """
    Model to track recordings and streams.
    """
    TYPE_CHOICES = [
        ('file', 'File Recording'),
        ('stream', 'Live Stream'),
        ('local', 'Local Recording'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('recording', 'Recording'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    conference = models.ForeignKey(Conference, on_delete=models.CASCADE,
                                    related_name='recordings')
    recording_type = models.CharField(max_length=20, choices=TYPE_CHOICES, 
                                       default='file')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES,
                               default='pending')
    
    # Recording details
    session_id = models.CharField(max_length=255, unique=True)
    file_path = models.CharField(max_length=500, blank=True)
    file_size_mb = models.FloatField(default=0)
    duration_seconds = models.IntegerField(default=0)
    
    # Stream details (if streaming)
    stream_url = models.URLField(blank=True)
    
    # Timestamps
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Error tracking
    error_message = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Recording"
        verbose_name_plural = "Recordings"
    
    def __str__(self):
        return f"{self.recording_type} - {self.conference.room_name} ({self.status})"


class WebhookEvent(models.Model):
    """
    Model to log all webhook events from Jitsi.
    Useful for debugging and analytics.
    """
    EVENT_TYPES = [
        ('ROOM_CREATED', 'Room Created'),
        ('ROOM_DESTROYED', 'Room Destroyed'),
        ('PARTICIPANT_JOINED', 'Participant Joined'),
        ('PARTICIPANT_LEFT', 'Participant Left'),
        ('PARTICIPANT_JOINED_LOBBY', 'Participant Joined Lobby'),
        ('PARTICIPANT_LEFT_LOBBY', 'Participant Left Lobby'),
        ('RECORDING_STARTED', 'Recording Started'),
        ('RECORDING_STOPPED', 'Recording Stopped'),
        ('OTHER', 'Other'),
    ]
    
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES)
    server = models.ForeignKey(JitsiServer, on_delete=models.CASCADE,
                                related_name='webhook_events', null=True)
    room_name = models.CharField(max_length=255, blank=True, db_index=True)
    payload = models.JSONField(default=dict)
    
    received_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-received_at']
        verbose_name = "Webhook Event"
        verbose_name_plural = "Webhook Events"
        indexes = [
            models.Index(fields=['event_type']),
            models.Index(fields=['received_at']),
        ]
    
    def __str__(self):
        return f"{self.event_type} - {self.room_name} at {self.received_at}"


class DashboardSettings(models.Model):
    """
    Singleton model for dashboard configuration.
    """
    refresh_interval_seconds = models.IntegerField(default=5,
                                                    help_text="Stats refresh interval")
    default_jwt_expiry_hours = models.IntegerField(default=24)
    enable_webhooks = models.BooleanField(default=True)
    webhook_secret = models.CharField(max_length=255, blank=True,
                                       help_text="Secret for webhook validation")
    
    # UI preferences
    dark_mode = models.BooleanField(default=True)
    show_bandwidth_graphs = models.BooleanField(default=True)
    max_recent_conferences = models.IntegerField(default=50)
    
    # Notifications
    notify_on_new_conference = models.BooleanField(default=False)
    notify_on_high_load = models.BooleanField(default=True)
    high_load_threshold = models.FloatField(default=0.8,
                                             help_text="Stress level threshold (0-1)")
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Dashboard Settings"
        verbose_name_plural = "Dashboard Settings"
    
    def save(self, *args, **kwargs):
        self.pk = 1  # Ensure singleton
        super().save(*args, **kwargs)
    
    @classmethod
    def get_settings(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj
    
    def __str__(self):
        return "Dashboard Settings"
