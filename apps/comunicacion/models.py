from django.db import models

from apps.core.models import BaseModel


class ChatConversacion(BaseModel):
    class Estado(models.TextChoices):
        ABIERTA = 'ABIERTA', 'Abierta'
        CERRADA = 'CERRADA', 'Cerrada'

    comprador = models.ForeignKey('usuarios.Comprador', on_delete=models.CASCADE, related_name='conversaciones')
    empresa = models.ForeignKey('usuarios.Empresa', on_delete=models.CASCADE, related_name='conversaciones')
    empleado_asignado = models.ForeignKey(
        'usuarios.Empleado', on_delete=models.SET_NULL, null=True, blank=True, related_name='conversaciones_asignadas'
    )
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.ABIERTA)

    class Meta:
        verbose_name = 'Conversación'
        verbose_name_plural = 'Conversaciones'

    def __str__(self):
        return f'Conversación #{self.id} - {self.comprador} / {self.empresa}'


class ChatMensaje(models.Model):
    class Tipo(models.TextChoices):
        TEXTO = 'TEXTO', 'Texto'
        IMAGEN = 'IMAGEN', 'Imagen'

    conversacion = models.ForeignKey(ChatConversacion, on_delete=models.CASCADE, related_name='mensajes')
    emisor_usuario = models.ForeignKey('usuarios.Usuario', on_delete=models.CASCADE, related_name='mensajes_enviados')
    contenido = models.TextField()
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.TEXTO)
    fecha_envio = models.DateTimeField(auto_now_add=True)
    leido = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Mensaje de chat'
        verbose_name_plural = 'Mensajes de chat'
        ordering = ['fecha_envio']

    def __str__(self):
        return f'{self.emisor_usuario.email}: {self.contenido[:30]}'


class ChatbotInteraccion(models.Model):
    comprador = models.ForeignKey(
        'usuarios.Comprador', on_delete=models.SET_NULL, null=True, blank=True, related_name='interacciones_chatbot'
    )
    pregunta = models.TextField()
    respuesta = models.TextField(blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Interacción con chatbot'
        verbose_name_plural = 'Interacciones con chatbot'

    def __str__(self):
        return self.pregunta[:50]
