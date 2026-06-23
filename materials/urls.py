"""
URL configuration for the materials app.
"""

from django.urls import path
from . import views

app_name = 'materials'

urlpatterns = [
    # Materials CRUD
    path('', views.MaterialListCreateView.as_view(), name='material_list'),
    path('<uuid:pk>/', views.MaterialDetailView.as_view(), name='material_detail'),
    path('<uuid:pk>/download/', views.MaterialDownloadView.as_view(), name='material_download'),

    # Progress
    path('<uuid:pk>/progress/', views.MaterialProgressView.as_view(), name='material_progress'),
    path('my/progress/', views.MyProgressView.as_view(), name='my_progress'),

    # Comments
    path('<uuid:pk>/comments/', views.MaterialCommentListCreateView.as_view(), name='comment_list'),

    # Bookmarks
    path('<uuid:pk>/bookmark/', views.MaterialBookmarkView.as_view(), name='bookmark_toggle'),
    path('my/bookmarks/', views.MyBookmarksView.as_view(), name='my_bookmarks'),

    # Ratings
    path('<uuid:pk>/rate/', views.MaterialRatingView.as_view(), name='rate_material'),
]
