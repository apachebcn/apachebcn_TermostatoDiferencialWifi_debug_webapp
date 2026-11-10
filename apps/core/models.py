import uuid

from django.contrib.auth.models import User
from django.db import models
from django.db.models.functions import TruncSecond
from django.utils import timezone


class UserProfile(models.Model):
    """Perfil del usuario: guarda su apikey única (una por usuario)."""

    class Meta:
        verbose_name = 'Perfil de usuario'
        verbose_name_plural = 'Perfiles de usuario'

    def __str__(self):
        return f"Perfil de {self.user.username}"

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    apikey = models.CharField(max_length=100, blank=False, null=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)


def generate_apikey(user):
    return f"{user.username}-{uuid.uuid4()}"


class InputDataHistory(models.Model):
    """
    Registro histórico de los datos enviados por el ESP32.

    'data' almacena TODOS los parámetros recibidos (excepto la apikey) como
    JSON, exactamente con los nombres/valores que envía el dispositivo. Los
    relés/sondas desactivados simplemente no se incluyen.
    """

    class Meta:
        verbose_name = 'Historial de datos de entrada'
        verbose_name_plural = 'Historiales de datos de entrada'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['user_id', '-created_at'], name='idh_user_created_idx'),
        ]
        constraints = [
            # Un único registro por usuario y segundo.
            models.UniqueConstraint(
                models.F('user_id'),
                TruncSecond('created_at'),
                name='unique_user_created_at_second',
            ),
        ]

    def __str__(self):
        created = ''
        if self.created_at:
            created = timezone.localtime(self.created_at).strftime('%Y-%m-%d %H:%M:%S')
        return f"Dato de {self.user_id.username} @ {created}"

    def save(self, *args, **kwargs):
        if not self.created_at:
            self.created_at = timezone.now()
        super().save(*args, **kwargs)

    user_id = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='input_data_history',
    )
    created_at = models.DateTimeField(blank=True, null=True)
    data = models.JSONField(blank=True, null=True, default=dict)
