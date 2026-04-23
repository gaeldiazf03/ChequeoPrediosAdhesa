# API Chequeo Predios

Backend Express conectado a MariaDB para autenticación, privilegios y gestión de predios.

## Endpoints principales

- POST /auth/login
- GET /properties
- PUT /properties/:propertyId
- PUT /properties/:propertyId/nodes
- POST /properties/:propertyId/watering
- GET /users (solo rol admin)
- POST /users (solo rol admin)
- GET /health

## Arranque

1. Copia `.env.example` a `.env`.
2. Ajusta `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` y `JWT_SECRET`.
3. Ejecuta `npm install`.
4. Ejecuta `npm run seed:admin`.
5. Ejecuta `npm run dev`.

## Cuenta MariaDB recomendada

La API no debe usar `root` en desarrollo. Crea un usuario dedicado, por ejemplo `chequeo_app`, y dale permisos sobre la base `chequeo_predios`.

Ejemplo de SQL:

```sql
CREATE USER 'chequeo_app'@'localhost' IDENTIFIED BY 'change-me';
GRANT ALL PRIVILEGES ON chequeo_predios.* TO 'chequeo_app'@'localhost';
FLUSH PRIVILEGES;
```

## Seed admin

Por defecto crea o actualiza:

- Usuario: admin
- Contraseña: EntrarAAdhesa_AhoraMismo!2026

Puedes cambiarlo con `ADMIN_USERNAME`, `ADMIN_EMAIL`, `ADMIN_NAME` y `ADMIN_PASSWORD` en `.env`.

Nota: el login es por usuario. El correo queda opcional para reportes posteriores.
