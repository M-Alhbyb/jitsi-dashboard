import json
import logging
from datetime import timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Count, Sum, Avg
from django.contrib import messages

from .models import (
    JitsiServer, Conference, Participant, 
    Recording, WebhookEvent, DashboardSettings
)
from .jitsi_api import JitsiAPI, JitsiServerConfig, get_jitsi_api

logger = logging.getLogger(__name__)


# ==================== DASHBOARD VIEWS ====================

def dashboard_home(request):
    """Main dashboard overview page."""
    context = {}
    
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
    
    return render(request, 'dashboard/home.html', context)


def conference_list(request):
    """List all conferences with filtering."""
    queryset = Conference.objects.select_related('server', 'created_by')
    
    # Filter by status
    status = request.GET.get('status')
    if status:
        queryset = queryset.filter(status=status)
    
    # Filter by server
    server_id = request.GET.get('server')
    if server_id:
        queryset = queryset.filter(server_id=server_id)
    
    # Search
    search = request.GET.get('q')
    if search:
        queryset = queryset.filter(room_name__icontains=search)
    
    queryset = queryset.order_by('-started_at')
    
    # Pagination
    paginator = Paginator(queryset, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'conferences': page_obj,
        'page_obj': page_obj,
        'servers': JitsiServer.objects.filter(is_active=True),
        'status_choices': Conference.STATUS_CHOICES,
    }
    return render(request, 'dashboard/conferences/list.html', context)


def conference_detail(request, pk):
    """View details of a specific conference."""
    conference = get_object_or_404(Conference, pk=pk)
    context = {
        'conference': conference,
        'participants': conference.participants.all(),
        'recordings': conference.recordings.all(),
    }
    return render(request, 'dashboard/conferences/detail.html', context)


def create_meeting(request):
    """Create a new meeting with JWT."""
    if request.method == 'POST':
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
    
    # GET request
    context = {
        'servers': JitsiServer.objects.filter(is_active=True)
    }
    return render(request, 'dashboard/conferences/create.html', context)


def participant_list(request):
    """List all participants across conferences."""
    queryset = Participant.objects.select_related('conference', 'user')
    
    # Filter by conference
    conf_id = request.GET.get('conference')
    if conf_id:
        queryset = queryset.filter(conference_id=conf_id)
    
    # Active only
    if request.GET.get('active'):
        queryset = queryset.filter(left_at__isnull=True)
    
    queryset = queryset.order_by('-joined_at')
    
    # Pagination
    paginator = Paginator(queryset, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'participants': page_obj,
        'page_obj': page_obj,
    }
    return render(request, 'dashboard/participants/list.html', context)


def recording_list(request):
    """List all recordings."""
    queryset = Recording.objects.select_related('conference')
    
    status = request.GET.get('status')
    if status:
        queryset = queryset.filter(status=status)
    
    queryset = queryset.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(queryset, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'recordings': page_obj,
        'page_obj': page_obj,
    }
    return render(request, 'dashboard/recordings/list.html', context)


def analytics(request):
    """Analytics and reporting page."""
    # Time range
    days = int(request.GET.get('days', 30))
    start_date = timezone.now() - timedelta(days=days)
    
    # Conference stats
    conferences = Conference.objects.filter(started_at__gte=start_date)
    total_conferences = conferences.count()
    total_participants = Participant.objects.filter(
        joined_at__gte=start_date
    ).count()
    
    # Average meeting duration
    completed = conferences.filter(status='ended', ended_at__isnull=False)
    avg_duration = 0
    if completed.exists():
        durations = [c.duration for c in completed]
        avg_duration = sum(durations) / len(durations)
    avg_duration_minutes = round(avg_duration, 1)
    
    # Peak participants
    max_participants = conferences.aggregate(
        max_p=Sum('max_participants')
    )['max_p'] or 0
    
    # Daily conference counts for chart
    daily_data = []
    for i in range(days, -1, -1):
        date = (timezone.now() - timedelta(days=i)).date()
        count = conferences.filter(started_at__date=date).count()
        daily_data.append({
            'date': date.strftime('%Y-%m-%d'),
            'count': count
        })
    
    context = {
        'total_conferences': total_conferences,
        'total_participants': total_participants,
        'avg_duration_minutes': avg_duration_minutes,
        'peak_participants': max_participants,
        'daily_data': json.dumps(daily_data),
        'days': days,
    }
    return render(request, 'dashboard/analytics.html', context)


def settings_view(request):
    """Dashboard settings page."""
    if request.method == 'POST':
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
    
    context = {
        'settings': DashboardSettings.get_settings(),
        'servers': JitsiServer.objects.all(),
    }
    return render(request, 'dashboard/settings.html', context)


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
