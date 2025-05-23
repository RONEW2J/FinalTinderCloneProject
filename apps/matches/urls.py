# apps/matches/urls.py
from django.urls import path
from . import views, views_api
from .views_api import SwipeActionView

app_name = 'matches'

urlpatterns = [
    # API Endpoints
    path('api/matches/', views_api.MatchListView.as_view(), name='api-matches-list'),
    path('api/conversations/', views_api.ConversationListView.as_view(), name='api-conversations-list'),
    path('api/conversations/<int:id>/', views_api.ConversationDetailView.as_view(), name='api-conversation-detail'),
    path('api/conversations/<int:conversation_id>/messages/', views_api.MessageListView.as_view(), name='api-messages-list'),
    path('api/actions/unmatch/<int:user_id>/', views_api.UnmatchView.as_view(), name='api-unmatch'),
    path('api/swipe/<int:profile_id>/<str:action>/', views_api.SwipeActionView.as_view(), name='api-swipe'),
    
    # UI Endpoints
    path('', views.list_matches_view, name='matches-list'),
    path('chat/', views.chat_view, name='chat-list'),
    path('chat/<int:conversation_id>/', views.chat_detail_view, name='chat-detail'),
    path('send-message/<int:conversation_id>/', views.send_message_view, name='send-message'),
    path('conversations/create/<int:target_user_id>/', views.create_or_get_conversation_view, name='create_conversation'),
]