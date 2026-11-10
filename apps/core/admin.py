from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.utils import timezone

from .models import InputDataHistory, UserProfile


def format_datetime_with_seconds(value):
    """Fecha/hora local con segundos (el locale de Django no los muestra)."""
    if not value:
        return ''
    return timezone.localtime(value).strftime('%Y-%m-%d %H:%M:%S')


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Perfil / apikey'
    fields = ('apikey', 'created_at_seconds')
    readonly_fields = ('apikey', 'created_at_seconds')

    @admin.display(description='Fecha de creación')
    def created_at_seconds(self, obj):
        return format_datetime_with_seconds(getattr(obj, 'created_at', None))


class CustomUserAdmin(UserAdmin):
    inlines = (UserProfileInline,)


admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'apikey', 'created_at_seconds')
    search_fields = ('user__username', 'apikey')
    exclude = ('created_at',)
    readonly_fields = ('apikey', 'created_at_seconds')

    @admin.display(description='Fecha de creación', ordering='created_at')
    def created_at_seconds(self, obj):
        return format_datetime_with_seconds(obj.created_at)


@admin.register(InputDataHistory)
class InputDataHistoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'user_id', 'created_at_seconds', 'data_preview')
    list_filter = ('user_id', 'created_at')
    search_fields = ('user_id__username',)
    date_hierarchy = 'created_at'
    fields = ('user_id', 'created_at_seconds', 'data')
    readonly_fields = ('user_id', 'created_at_seconds', 'data')

    @admin.display(description='Fecha/hora', ordering='created_at')
    def created_at_seconds(self, obj):
        return format_datetime_with_seconds(obj.created_at)

    @admin.display(description='Datos')
    def data_preview(self, obj):
        import json

        text = json.dumps(obj.data or {}, ensure_ascii=False, sort_keys=True)
        return text if len(text) <= 150 else text[:150] + '…'
