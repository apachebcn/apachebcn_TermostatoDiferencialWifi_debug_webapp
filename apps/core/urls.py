from django.urls import path

from . import views

urlpatterns = [
    # Login propio
    path('form_login/', views.form_login, name='form_login'),
    path('logout/', views.form_logout, name='form_logout'),

    # Ruta usada por el firmware debug del ESP32 (sin barra final).
    path('insert', views.insert_input_data_view, name='insert_input_data_view'),
    path('insert/', views.insert_input_data_view, name='insert_input_data_view_slash'),
    # Alias compatible con la app original.
    path('api/insert_thermostate_data/', views.insert_input_data_view, name='insert_input_data_view'),
    path('history_data_graph_view/', views.history_data_graph_view, name='history_data_graph_view'),
    path('get_json_data_graph_view/', views.get_json_data_graph_view, name='get_json_data_graph_view'),
    path('get_nearest_data_day_view/', views.get_nearest_data_day_view, name='get_nearest_data_day_view'),
    path('data_history_export/', views.data_history_export_view, name='data_history_export_view'),
    path('data_history_delete_range/', views.data_history_delete_range_view, name='data_history_delete_range_view'),
    path('data_history_delete_all/', views.data_history_delete_all_view, name='data_history_delete_all_view'),
]
