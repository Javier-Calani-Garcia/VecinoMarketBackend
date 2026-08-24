# Modelos de la app "reportes" (Reportes, dashboard e IA).
# Hereda de apps.core.models.TenantModel para quedar aislado por empresa,
# o de BaseModel si el modelo no pertenece a un tenant específico.
#
# from apps.core.models import TenantModel
#
# class MiModelo(TenantModel):
#     nombre = models.CharField(max_length=150)
