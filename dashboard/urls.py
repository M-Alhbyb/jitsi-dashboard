from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    # Dashboard pages
    path('', views.DashboardHomeView.as_view(), name='home'),
    
    # Conferences
    path('conferences/', views.ConferenceListView.as_view(), name='conferences'),
    path('conferences/<int:pk>/', views.ConferenceDetailView.as_view(), name='conference_detail'),
    path('conferences/create/', views.CreateMeetingView.as_view(), name='create_meeting'),
    
    # Participants
    path('participants/', views.ParticipantListView.as_view(), name='participants'),
    
    # Recordings
    path('recordings/', views.RecordingListView.as_view(), name='recordings'),
    
    # Analytics
    path('analytics/', views.AnalyticsView.as_view(), name='analytics'),
    
    # Settings
    path('settings/', views.SettingsView.as_view(), name='settings'),
    
    # API endpoints
    path('api/stats/', views.api_server_stats, name='api_stats'),
    path('api/colibri/', views.api_colibri_stats, name='api_colibri'),
    path('api/token/', views.api_generate_token, name='api_token'),
    path('api/recording/start/', views.api_start_recording, name='api_recording_start'),
    path('api/recording/stop/', views.api_stop_recording, name='api_recording_stop'),
    
    # Webhooks
    path('webhooks/', views.webhook_handler, name='webhook_handler'),
]
