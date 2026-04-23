# MariaDB

Este directorio contiene el esquema inicial de MariaDB para Chequeo Predios.

## Tablas principales

- `users`: usuarios (login por username), contraseñas hasheadas, email opcional para reportes, rol y estado activo.
- `user_privileges`: permisos finos para edición de responsables, nodos, riego, plantación, cultivo y nombre del predio.
- `properties`: predios con responsable, cultivo, si es caña, fecha de plantación y último riego.
- `property_nodes`: nodos del contorno geográfico del predio.
- `watering_logs`: historial de riego por predio.

## Uso

1. Crea una base MariaDB compatible con `utf8mb4`.
2. Ejecuta [schema.sql](mariadb/schema.sql).
3. Conecta tu API privada al esquema y expón solo los endpoints necesarios para el frontend.

## Nota de seguridad

Las contraseñas deben guardarse como hash, nunca en texto plano. El frontend no debe acceder directamente a MariaDB.