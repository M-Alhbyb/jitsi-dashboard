from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    # Dashboard pages
    path('', views.dashboard_home, name='home'),
    
    # Conferences
    path('conferences/', views.conference_list, name='conferences'),
    path('conferences/<int:pk>/', views.conference_detail, name='conference_detail'),
    path('conferences/create/', views.create_meeting, name='create_meeting'),
    
    # Participants
    path('participants/', views.participant_list, name='participants'),
    
    # Recordings
    path('recordings/', views.recording_list, name='recordings'),
    
    # Analytics
    path('analytics/', views.analytics, name='analytics'),
    
    # Settings
    path('settings/', views.settings_view, name='settings'),
    
    # API endpoints
    path('api/stats/', views.api_server_stats, name='api_stats'),
    path('api/colibri/', views.api_colibri_stats, name='api_colibri'),
    path('api/token/', views.api_generate_token, name='api_token'),
    path('api/recording/start/', views.api_start_recording, name='api_recording_start'),
    path('api/recording/stop/', views.api_stop_recording, name='api_recording_stop'),
    
    # Webhooks
    path('webhooks/', views.webhook_handler, name='webhook_handler'),
]
