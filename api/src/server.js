import cors from 'cors'
import express from 'express'
import helmet from 'helmet'
import morgan from 'morgan'
import { config } from './config.js'
import { healthCheckDb } from './db.js'
import { authRoutes } from './routes/authRoutes.js'
import { propertyRoutes } from './routes/propertyRoutes.js'
import { lotRoutes } from './routes/lotRoutes.js'
import { userRoutes } from './routes/userRoutes.js'

const app = express()

app.use(
  cors({
    origin: true,
    credentials: true,
  }),
)
app.use(helmet())
app.use(morgan('dev'))
app.use(express.json({ limit: '1mb' }))
app.use(
  express.text({
    limit: '1mb',
    type: (req) => {
      const contentType = req.headers['content-type'] ?? ''
      return !String(contentType).includes('application/json')
    },
  }),
)
app.use((req, _res, next) => {
  if (typeof req.body === 'string') {
    const trimmedBody = req.body.trim()

    if (trimmedBody.startsWith('{') || trimmedBody.startsWith('[')) {
      try {
        req.body = JSON.parse(trimmedBody)
      } catch {
        // Leave non-JSON text bodies untouched for routes that may need them.
      }
    }
  }

  next()
})

app.get('/health', async (_req, res) => {
  try {
    await healthCheckDb()
    return res.json({ ok: true })
  } catch (error) {
    console.error('Health check failed', error)
    return res.status(500).json({ ok: false })
  }
})

app.use('/auth', authRoutes)
app.use('/properties', propertyRoutes)
app.use('/lots', lotRoutes)
app.use('/users', userRoutes)

app.use((_req, res) => {
  return res.status(404).json({ error: 'Not found' })
})

app.listen(config.port, () => {
  console.log(`Chequeo Predios API listening on port ${config.port}`)
})
