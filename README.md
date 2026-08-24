# VecinoMarket — Backend

Backend en Django + Django REST Framework + PostgreSQL para la plataforma
multi-tenant de gestión de emprendimientos locales VecinoMarket.

## Arquitectura de roles

- **Superadministrador**: gestiona la plataforma, crea las cuentas de empresa (tenants).
- **Admin de empresa**: dueño del tenant, creado por el superadmin. Crea a sus empleados.
- **Empleado**: creado por el admin de empresa, con permisos granulares por módulo.
- **Cliente**: se autoregistra, no pertenece a ningún tenant.

Multi-tenancy por fila (shared schema): todo modelo de negocio hereda de
`apps.core.models.TenantModel`, que agrega un FK obligatorio a `Empresa`.

## Puesta en marcha local

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate

pip install -r requirements/dev.txt

cp .env.example .env
# edita .env con tus credenciales reales de PostgreSQL

python manage.py makemigrations
python manage.py migrate
python manage.py crear_superadmin --email admin@vecinomarket.com --password TU_PASSWORD

python manage.py runserver
```

## Base de datos

Crea la base y el usuario en PostgreSQL antes de migrar:

```sql
CREATE DATABASE vecinomarket;
CREATE USER vecinomarket WITH PASSWORD 'password';
GRANT ALL PRIVILEGES ON DATABASE vecinomarket TO vecinomarket;
```

## Endpoints principales (`/api/usuarios/`)

| Método | Ruta                                   | Quién                | Descripción                          |
|--------|-----------------------------------------|-----------------------|---------------------------------------|
| POST   | `auth/login/`                          | Todos                 | Login, devuelve JWT con rol y empresa |
| POST   | `auth/refresh/`                        | Todos                 | Refresca el access token              |
| GET    | `auth/perfil/`                         | Autenticado            | Datos del usuario actual              |
| POST   | `empresas/`                            | Superadmin             | Crea empresa + su admin               |
| POST   | `empleados/`                           | Admin de empresa       | Crea empleado en su tenant            |
| POST   | `empleados/<id>/desactivar/`           | Admin de empresa       | Desactiva empleado y revoca sesión    |
| POST   | `empleados/<id>/reactivar/`            | Admin de empresa       | Reactiva empleado                     |
| POST   | `clientes/registro/`                   | Público                | Autoregistro de cliente               |

## Estructura de apps

Cada app corresponde a un paquete del documento de alcance del proyecto:

- `core` — modelos base, middleware de tenant, utilidades compartidas.
- `usuarios` — Paquete 1: usuarios y seguridad.
- `catalogo` — Paquete 2: catálogo y productos.
- `inventario`, `pedidos` — Paquete 3: inventario, pedidos y ventas.
- `comunicacion`, `promociones` — Paquete 4: comunicación, marketing y live commerce.
- `reportes`, `auditoria` — Paquete 5: reportes, IA y auditoría.
- `notificaciones`, `suscripciones`, `facturacion` — módulos transversales.

## Siguientes pasos

1. Definir los modelos de `catalogo` (Categoria, Producto) heredando de `TenantModel`.
2. Repetir para `inventario`, `pedidos`, etc.
3. Conectar cada `urls.py` de app en `config/urls.py`.
