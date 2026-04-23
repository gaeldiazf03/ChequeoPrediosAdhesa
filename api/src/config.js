import dotenv from 'dotenv'

dotenv.config()

function requireValue(name, fallback) {
  const value = process.env[name] ?? fallback

  if (value === undefined || value === '') {
    throw new Error(`Missing environment variable: ${name}`)
  }

  return value
}

export const config = {
  port: Number(process.env.API_PORT ?? 4000),
  jwtSecret: requireValue('JWT_SECRET', undefined),
  db: {
    host: requireValue('DB_HOST', '127.0.0.1'),
    port: Number(process.env.DB_PORT ?? 3306),
    user: requireValue('DB_USER', 'chequeo_app'),
    password: process.env.DB_PASSWORD ?? '',
    database: requireValue('DB_NAME', 'chequeo_predios'),
  },
}
