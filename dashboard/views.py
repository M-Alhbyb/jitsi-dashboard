import json
import logging
from datetime import timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views import View
from django.views.generic import TemplateView, ListView, DetailView
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.db.models import Count, Sum, Avg
from django.contrib import messages

from .models import (
    JitsiServer, Conference, Participant, 
    Recording, WebhookEvent, DashboardSettings
)
from .jitsi_api import JitsiAPI, JitsiServerConfig, get_jitsi_api

logger = logging.getLogger(__name__)


# ==================== DASHBOARD VIEWS ====================

class DashboardHomeView(TemplateView):
    """Main dashboard overview page."""
    template_name = 'dashboard/home.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get primary server stats
        try:
            api = get_jitsi_api()
            server_overview = api.get_server_overview()
            context['server_overview'] = server_overview
            context['api_connected'] = True
        except Exception as e:
            logger.error(f"Failed to get server overview: {e}")
            context['api_connected'] = False
            context['api_error'] = str(e)
        
        # Get database stats
        context['recent_conferences'] = Conference.objects.filter(
            started_at__gte=timezone.now() - timedelta(days=7)
        ).order_by('-started_at')[:10]
        
        context['active_conferences'] = Conference.objects.filter(
            status='active'
        ).count()
        
        context['total_participants_today'] = Participant.objects.filter(
            joined_at__date=timezone.now().date()
        ).count()
        
        # Get all servers
        context['servers'] = JitsiServer.objects.filter(is_active=True)
        
        # Dashboard settings
        context['settings'] = DashboardSettings.get_settings()
        
        return context


class ConferenceListView(ListView):
    """List all conferences with filtering."""
    model = Conference
    template_name = 'dashboard/conferences/list.html'
    context_object_name = 'conferences'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Conference.objects.select_related('server', 'created_by')
        
        # Filter by status
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Filter by server
        server_id = self.request.GET.get('server')
        if server_id:
            queryset = queryset.filter(server_id=server_id)
        
        # Search
        search = self.request.GET.get('q')
        if search:
            queryset = queryset.filter(room_name__icontains=search)
        
        return queryset.order_by('-started_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['servers'] = JitsiServer.objects.filter(is_active=True)
        context['status_choices'] = Conference.STATUS_CHOICES
        return context


class ConferenceDetailView(DetailView):
    """View details of a specific conference."""
    model = Conference
    template_name = 'dashboard/conferences/detail.html'
    context_object_name = 'conference'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['participants'] = self.object.participants.all()
        context['recordings'] = self.object.recordings.all()
        return context


class CreateMeetingView(TemplateView):
    """Create a new meeting with JWT."""
    template_name = 'dashboard/conferences/create.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['servers'] = JitsiServer.objects.filter(is_active=True)
        return context
    
    def post(self, request, *args, **kwargs):
        room_name = request.POST.get('room_name', '').strip()
        display_name = request.POST.get('display_name', '')
        user_name = request.POST.get('user_name', 'Moderator')
        user_email = request.POST.get('user_email', '')
        server_id = request.POST.get('server')
        enable_lobby = request.POST.get('enable_lobby') == 'on'
        enable_password = request.POST.get('enable_password') == 'on'
        password = request.POST.get('password', '')
        
        if not room_name:
            messages.error(request, "Room name is required")
            return redirect('dashboard:create_meeting')
        
        try:
            # Get server
            if server_id:
                server = JitsiServer.objects.get(pk=server_id)
            else:
                server = JitsiServer.objects.filter(is_primary=True).first()
                if not server:
                    server = JitsiServer.objects.filter(is_active=True).first()
            
            if not server:
                messages.error(request, "No active Jitsi server configured")
                return redirect('dashboard:create_meeting')
            
            # Create API client for this server
            config = JitsiServerConfig(
                base_url=server.base_url,
                app_id=server.app_id,
                app_secret=server.app_secret
            )
            api = JitsiAPI(config)
            
            # Generate meeting URL
            meeting_url = api.generate_meeting_url(
                room_name=room_name,
                user_name=user_name,
                user_email=user_email,
                is_moderator=True,
                use_jwt=bool(server.app_secret)
            )
            
            # Create conference record
            conference = Conference.objects.create(
                server=server,
                room_name=room_name.replace(" ", "-").lower(),
                display_name=display_name or room_name,
                status='scheduled',
                created_by=request.user if request.user.is_authenticated else None,
                has_lobby=enable_lobby,
                is_password_protected=enable_password
            )
            
            context = {
                'conference': conference,
                'meeting_url': meeting_url,
                'server': server
            }
            return render(request, 'dashboard/conferences/created.html', context)
            
        except Exception as e:
            logger.error(f"Failed to create meeting: {e}")
            messages.error(request, f"Failed to create meeting: {e}")
            return redirect('dashboard:create_meeting')


class ParticipantListView(ListView):
    """List all participants across conferences."""
    model = Participant
    template_name = 'dashboard/participants/list.html'
    context_object_name = 'participants'
    paginate_by = 50
    
    def get_queryset(self):
        queryset = Participant.objects.select_related('conference', 'user')
        
        # Filter by conference
        conf_id = self.request.GET.get('conference')
        if conf_id:
            queryset = queryset.filter(conference_id=conf_id)
        
        # Active only
        if self.request.GET.get('active'):
            queryset = queryset.filter(left_at__isnull=True)
        
        return queryset.order_by('-joined_at')


class RecordingListView(ListView):
    """List all recordings."""
    model = Recording
    template_name = 'dashboard/recordings/list.html'
    context_object_name = 'recordings'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Recording.objects.select_related('conference')
        
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        return queryset.order_by('-created_at')


class AnalyticsView(TemplateView):
    """Analytics and reporting page."""
    template_name = 'dashboard/analytics.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Time range
        days = int(self.request.GET.get('days', 30))
        start_date = timezone.now() - timedelta(days=days)
        
        # Conference stats
        conferences = Conference.objects.filter(started_at__gte=start_date)
        context['total_conferences'] = conferences.count()
        context['total_participants'] = Participant.objects.filter(
            joined_at__gte=start_date
        ).count()
        
        # Average meeting duration
        completed = conferences.filter(status='ended', ended_at__isnull=False)
        avg_duration = 0
        if completed.exists():
            durations = [c.duration for c in completed]
            avg_duration = sum(durations) / len(durations)
        context['avg_duration_minutes'] = round(avg_duration, 1)
        
        # Peak participants
        max_participants = conferences.aggregate(
            max_p=Sum('max_participants')
        )['max_p'] or 0
        context['peak_participants'] = max_participants
        
        # Daily conference counts for chart
        daily_data = []
        for i in range(days, -1, -1):
            date = (timezone.now() - timedelta(days=i)).date()
            count = conferences.filter(started_at__date=date).count()
            daily_data.append({
                'date': date.strftime('%Y-%m-%d'),
                'count': count
            })
        context['daily_data'] = json.dumps(daily_data)
        
        context['days'] = days
        return context


class SettingsView(TemplateView):
    """Dashboard settings page."""
    template_name = 'dashboard/settings.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['settings'] = DashboardSettings.get_settings()
        context['servers'] = JitsiServer.objects.all()
        return context
    
    def post(self, request, *args, **kwargs):
        settings = DashboardSettings.get_settings()
        
        settings.refresh_interval_seconds = int(
            request.POST.get('refresh_interval', 5)
        )
        settings.default_jwt_expiry_hours = int(
            request.POST.get('jwt_expiry', 24)
        )
        settings.dark_mode = request.POST.get('dark_mode') == 'on'
        settings.show_bandwidth_graphs = request.POST.get('show_graphs') == 'on'
        settings.save()
        
        messages.success(request, "Settings saved successfully")
        return redirect('dashboard:settings')


# ==================== API ENDPOINTS ====================

@require_http_methods(["GET"])
def api_server_stats(request):
    """Get real-time server statistics."""
    try:
        api = get_jitsi_api()
        overview = api.get_server_overview()
        return JsonResponse(overview)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["GET"])
def api_colibri_stats(request):
    """Get JVB Colibri statistics."""
    try:
        api = get_jitsi_api()
        stats = api.get_colibri_stats()
        return JsonResponse(stats)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["POST"])
def api_generate_token(request):
    """Generate JWT token for a meeting."""
    try:
        data = json.loads(request.body)
        room_name = data.get('room_name', '')
        user_name = data.get('user_name', 'Guest')
        user_email = data.get('user_email', '')
        is_moderator = data.get('is_moderator', False)
        
        api = get_jitsi_api()
        token = api.generate_jwt_token(
            room_name=room_name,
            user_name=user_name,
            user_email=user_email,
            is_moderator=is_moderator
        )
        
        return JsonResponse({
            'success': True,
            'token': token
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@require_http_methods(["POST"])
def api_start_recording(request):
    """Start recording for a conference."""
    try:
        data = json.loads(request.body)
        room_name = data.get('room_name', '')
        mode = data.get('mode', 'file')
        stream_url = data.get('stream_url', '')
        
        api = get_jitsi_api()
        result = api.start_recording(
            room_name=room_name,
            mode=mode,
            stream_url=stream_url
        )
        
        return JsonResponse(result)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["POST"])
def api_stop_recording(request):
    """Stop current recording."""
    try:
        api = get_jitsi_api()
        result = api.stop_recording()
        return JsonResponse(result)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# ==================== WEBHOOK HANDLER ====================

@csrf_exempt
@require_http_methods(["POST"])
def webhook_handler(request):
    """Handle incoming webhooks from Jitsi."""
    try:
        data = json.loads(request.body)
        event_type = data.get('eventType', 'OTHER')
        room_name = data.get('roomName', '') or data.get('room', {}).get('name', '')
        
        # Log the event
        WebhookEvent.objects.create(
            event_type=event_type,
            room_name=room_name,
            payload=data
        )
        
        # Process specific event types
        if event_type == 'ROOM_CREATED':
            _handle_room_created(data)
        elif event_type == 'ROOM_DESTROYED':
            _handle_room_destroyed(data)
        elif event_type == 'PARTICIPANT_JOINED':
            _handle_participant_joined(data)
        elif event_type == 'PARTICIPANT_LEFT':
            _handle_participant_left(data)
        
        return JsonResponse({'status': 'ok'})
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return JsonResponse({'error': str(e)}, status=400)


def _handle_room_created(data):
    """Process room created event."""
    room_name = data.get('roomName', '') or data.get('room', {}).get('name', '')
    if not room_name:
        return
    
    # Get or create conference
    server = JitsiServer.objects.filter(is_primary=True).first()
    if not server:
        server = JitsiServer.objects.filter(is_active=True).first()
    
    if server:
        Conference.objects.update_or_create(
            room_name=room_name,
            server=server,
            defaults={
                'status': 'active',
                'started_at': timezone.now()
            }
        )


def _handle_room_destroyed(data):
    """Process room destroyed event."""
    room_name = data.get('roomName', '') or data.get('room', {}).get('name', '')
    if room_name:
        Conference.objects.filter(
            room_name=room_name,
            status='active'
        ).update(
            status='ended',
            ended_at=timezone.now()
        )


def _handle_participant_joined(data):
    """Process participant joined event."""
    room_name = data.get('roomName', '') or data.get('room', {}).get('name', '')
    participant_data = data.get('participant', {})
    
    if not room_name:
        return
    
    conference = Conference.objects.filter(
        room_name=room_name,
        status='active'
    ).first()
    
    if conference:
        Participant.objects.create(
            conference=conference,
            participant_id=participant_data.get('participantId', ''),
            name=participant_data.get('name', 'Unknown'),
            email=participant_data.get('email', ''),
            is_moderator=participant_data.get('moderator', False),
            joined_at=timezone.now()
        )
        
        # Update participant count
        current_count = conference.participants.filter(left_at__isnull=True).count()
        if current_count > conference.max_participants:
            conference.max_participants = current_count
            conference.save()


def _handle_participant_left(data):
    """Process participant left event."""
    room_name = data.get('roomName', '') or data.get('room', {}).get('name', '')
    participant_data = data.get('participant', {})
    participant_id = participant_data.get('participantId', '')
    
    if room_name and participant_id:
        Participant.objects.filter(
            conference__room_name=room_name,
            participant_id=participant_id,
            left_at__isnull=True
        ).update(
            left_at=timezone.now(),
            disconnect_reason=participant_data.get('disconnectReason', '')
        )
