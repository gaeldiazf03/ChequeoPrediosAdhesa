# React + TypeScript + Vite

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the ESLint configuration

If you are developing a production application, we recommend updating the configuration to enable type-aware lint rules:

```js
export default defineConfig([
  # Chequeo Predios

  Aplicación React + TypeScript para administración de cuentas, login y visualización/editado de predios sobre Google Maps, con foco inicial en México y la región Huasteca.

  ## Qué incluye

  - Login local para administrador, manager y viewer.
  - Administración básica de cuentas y privilegios desde el panel.
  - Visualizador de Google Maps centrado en México con contorno editable del predio.
  - Configuración visual desacoplada en JSON para colores, tipografías y tamaños.
  - Carpeta preparada para logotipos en `public/logos/`.

  ## Configuración

  1. Instala dependencias.
  2. Define la variable de entorno `VITE_GOOGLE_MAPS_API_KEY` con una clave válida de Google Maps.
  3. Ejecuta `npm run dev`.

  ## Archivos clave

  - Tema visual: `public/config/theme.json`
  - Logos: `public/logos/`
  - Entrada principal: `src/App.tsx`

  ## Credenciales de demo

  - Correo: `admin@chequeopredios.mx`
  - Contraseña: `Admin123!`

  ## Siguientes pasos

  Cuando quieras ampliar la base, se puede conectar este front-end a un backend real, agregar persistencia de cuentas y reemplazar las capas locales de edición por servicios de negocio.

