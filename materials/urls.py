"""
URL configuration for the materials app.
"""

from django.urls import path

from . import views

app_name = 'materials'

urlpatterns = [
    # Materials
    path('', views.MaterialListCreateView.as_view(), name='material_list'),
    path('<uuid:pk>/', views.MaterialDetailView.as_view(), name='material_detail'),

    # Progress
    path('<uuid:material_id>/progress/', views.UpdateProgressView.as_view(), name='update_progress'),
    path('my/progress/', views.MyProgressView.as_view(), name='my_progress'),

    # Comments
    path('<uuid:material_id>/comments/', views.CommentListCreateView.as_view(), name='comment_list'),

    # Bookmarks
    path('<uuid:material_id>/bookmark/', views.BookmarkToggleView.as_view(), name='bookmark_toggle'),
    path('my/bookmarks/', views.MyBookmarksView.as_view(), name='my_bookmarks'),

    # Ratings
    path('<uuid:material_id>/rate/', views.RateMaterialView.as_view(), name='rate_material'),
]
