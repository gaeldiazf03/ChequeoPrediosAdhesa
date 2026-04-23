# 🌾 Chequeo Predios - Plataforma GIS Agrícola

**Plataforma privada de gestión de predios agrícolas con visualización satelital de lotes clasificados por tipo de cultivo.**

---

## 📋 Descripción

Una solución web moderna para administración de predios azucareros y lotes agrícolas:

✅ **Predios georreferenciados** - Mapa satelital ArcGIS en tiempo real  
✅ **Lotes clasificados** - 7 tipos de clasificación real (caña soca 3y, 6y, siembra nueva, etc.)  
✅ **Control de acceso** - Admin edita; otros usuarios consultan (read-only)  
✅ **Interfaz GIS intuitiva** - Sidebar predios + mapa central + sidebar lotes  
✅ **API privada segura** - JWT + roles + BD MariaDB encriptada  

---

## 🚀 Inicio Rápido

### Requisitos
- Node.js 18+
- MariaDB 10.x+
- npm 9+

### 1. Instalar dependencias

```bash
# Frontend
npm install

# Backend
cd api && npm install
```

### 2. Configurar variables de entorno

**Raíz del proyecto** (`.env`):
```env
VITE_API_BASE_URL=http://localhost:4011
```

**Carpeta `api`** (`.env`):
```env
DB_HOST=localhost
DB_USER=chequeo_app
DB_PASSWORD=tu_contraseña_segura
DB_NAME=chequeo_predios

JWT_SECRET=tu_secreto_jwt_super_seguro_aqui
JWT_EXPIRATION=7d

PORT=4011
```

### 3. Crear base de datos

```bash
# Conectar a MariaDB
mysql -u root -p

# Crear BD y usuario
CREATE DATABASE chequeo_predios;
CREATE USER 'chequeo_app'@'localhost' IDENTIFIED BY 'tu_contraseña_segura';
GRANT ALL PRIVILEGES ON chequeo_predios.* TO 'chequeo_app'@'localhost';
FLUSH PRIVILEGES;
EXIT;

# Cargar schema
mysql -h localhost -u chequeo_app -p chequeo_predios < database/mariadb/schema.sql
```

### 4. Iniciar aplicación

**Terminal 1 - Backend:**
```bash
cd api
npm run start
```

**Terminal 2 - Frontend:**
```bash
npm run dev
```

### 5. Acceder

Abre `http://localhost:5173`

**Credenciales por defecto:**
- Usuario: `admin`
- Contraseña: (la configuraste en `.env` del admin)

---

## 📊 Datos de Prueba (Opcional)

Para cargar 3 predios con 9 lotes ficticios (incluyendo coordenadas GeoJSON):

```bash
cd api
npm run seed:test
```

---

## 👥 Gestión de Usuarios

### Crear nuevo usuario (Interactivo)

```bash
cd api
npm run create:user
```

Responde:
```
Usuario: gerente1
Nombre: Gerente Regional
Email: gerente@empresa.com
Rol: manager
Contraseña: mi_contraseña
```

**Roles disponibles:**
- **admin** - Crear/editar/eliminar predios, lotes, usuarios
- **manager** - Ver todo, editar predios (sin usuarios)
- **viewer** - Solo lectura (consulta)

---

## 🗺️ Características Principales

### 📍 Sidebar Izquierdo - Predios
- Lista completa de predios
- Crear predio (admin): nombre, responsable, región
- Eliminar predio (admin)
- Seleccionar para ver en mapa

### 🛰️ Panel Central - Mapa Satelital
- Mapa ArcGIS World Imagery (satelital)
- Polígonos coloreados de lotes
- Zoom y navegación
- Coordenadas en tiempo real

### 📦 Sidebar Derecho - Lotes
- Lista de lotes del predio seleccionado
- Color según clasificación
- Área en hectáreas y notas
- Crear lote (admin): nombre, clasificación, hectáreas, notas
- Eliminar lote (admin)

---

## 🎨 Clasificaciones de Lotes

| Código | Nombre | Color | Descripción |
|--------|--------|-------|-------------|
| NEW_PLANTING | Siembra Nueva | 🟢 | Caña recién plantada (0-6 meses) |
| SOCA_3Y | Caña Soca 3 Años | 🟡 | Cosechas iterativas 3 años |
| SOCA_6Y | Caña Soca 6 Años | 🟠 | Cosechas iterativas 6 años |
| SOCA_8Y_OLD | Caña Vieja/Soca 8+ | 🔴 | Soca muy vieja, productividad baja |
| PRODUCTIVE_NO_SUGARCANE | Área Productiva sin Caña | 🔵 | Cultivos alternativos |
| REST | Descanso/Rotación | ⚫ | En descanso de cultivo |
| NON_PRODUCTIVE | No Productivo | ⚪ | Caminos, servicios, no cultivable |

---

## 🔌 API Endpoints

### Autenticación
- `POST /auth/login` - Login con JWT
- Requiere: `{ username, password }`
- Retorna: `{ session, token }`

### Predios
- `GET /properties` - Listar todos (con lotes anidados)
- `POST /properties` - Crear predio (admin)
- `DELETE /properties/:id` - Eliminar (admin)

### Lotes
- `GET /lots/classifications` - Listar tipos
- `GET /lots/:propertyId` - Lotes de un predio
- `POST /lots` - Crear lote (admin)
- `PUT /lots/:id` - Actualizar (admin)
- `DELETE /lots/:id` - Eliminar (admin)

### Usuarios
- `GET /users` - Listar usuarios (admin)
- `POST /users` - Crear usuario (admin)
- `PUT /users/:id` - Actualizar (admin)
- `DELETE /users/:id` - Eliminar (admin)

---

## 📁 Estructura del Proyecto

```
chequeo-predios/
├── src/
│   ├── App.tsx              # Componente principal GIS
│   ├── App.css              # Estilos (layout 3-panel)
│   └── main.tsx
├── api/
│   ├── src/
│   │   ├── server.js        # Express principal
│   │   ├── db.js            # Pool MySQL
│   │   ├── routes/          # Endpoints
│   │   │   ├── authRoutes.js
│   │   │   ├── propertyRoutes.js
│   │   │   ├── lotRoutes.js
│   │   │   └── userRoutes.js
│   │   ├── middleware/
│   │   │   └── auth.js      # Verificar JWT
│   │   └── services/
│   │       └── authService.js
│   ├── scripts/
│   │   ├── migrateToLots.js     # Crear tablas lotes
│   │   ├── seedAdmin.js         # Usuario admin
│   │   ├── seedTestData.js      # Predios de prueba
│   │   └── createUser.js        # Crear usuario interactivo
│   └── package.json
├── database/
│   └── mariadb/
│       ├── schema.sql           # DDL completo
│       └── seed_test_data.sql   # Datos de prueba
├── public/
│   ├── config/
│   │   └── theme.json           # Configuración tema
│   └── logos/
├── dist/                        # Build frontend
├── .env                         # Variables entorno
└── README.md                    # Este archivo
```

---

## 🔐 Seguridad

- **Contraseñas:** Hash bcrypt (10 rounds)
- **Autenticación:** JWT Bearer token
- **Autorización:** Role-based middleware
- **CORS:** Habilitado solo para frontend
- **Helmet:** Headers de seguridad
- **Morgan:** Logging de requests
- **MySQL Prepared Statements:** Prevención SQL injection

---

## 🛠️ Desarrollo

### Build Frontend
```bash
npm run build
```

### Desarrollo Frontend (hot reload)
```bash
npm run dev
```

### Desarrollo Backend (hot reload)
```bash
cd api && npm run dev
```

### Migraciones
```bash
cd api && npm run migrate:lots   # Crear tablas lotes
cd api && npm run seed:admin     # Usuario admin
cd api && npm run seed:test      # Predios de prueba
```

---

## 📖 Documentación Adicional

Para pasos detallados sobre:
- Crear predios con coordenadas GeoJSON
- Editar lotes en mapa
- Gestión de usuarios
- Configuración avanzada

Ver: **[README_PASOS_ADICIONALES.md](README_PASOS_ADICIONALES.md)**

---

## 🐛 Troubleshooting

### "API no disponible"
```bash
cd api && npm run start
# Verifica que corra en puerto 4011
```

### "Cannot connect to database"
```bash
sudo systemctl start mariadb
# Verifica credenciales en .env
```

### "VITE_API_BASE_URL not configured"
- Crea `.env` en raíz con: `VITE_API_BASE_URL=http://localhost:4011`

### "Lotes no aparecen en mapa"
- ¿Tienen `coordinates_geojson` válido?
- ¿El GeoJSON tiene formato Polygon correcto?
- Revisa consola (F12) para errores

---

## 📝 Licencia

Privado - Proyecto agrícola

---

## 👨‍💻 Soporte

Para problemas o sugerencias, revisar logs en terminal y `.env` settings.

**Stack:**
- React 19 + TypeScript + Vite
- Node.js ESM + Express
- MariaDB 10.x
- Leaflet + ArcGIS Imagery

---

**Última actualización:** 17 de abril de 2026  
**Versión:** 1.0.0
