from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', RedirectView.as_view(pattern_name='history_data_graph_view', permanent=False)),
    path('', include('apps.core.urls')),
]
