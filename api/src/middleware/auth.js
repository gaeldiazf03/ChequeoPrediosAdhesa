import jwt from 'jsonwebtoken'
import { config } from '../config.js'

export function requireAuth(req, res, next) {
  const authorization = req.headers.authorization ?? ''

  if (!authorization.startsWith('Bearer ')) {
    return res.status(401).json({ error: 'Missing bearer token' })
  }

  const token = authorization.slice('Bearer '.length)

  try {
    const payload = jwt.verify(token, config.jwtSecret)
    req.auth = payload
    return next()
  } catch {
    return res.status(401).json({ error: 'Invalid token' })
  }
}

export function requireRole(...roles) {
  return (req, res, next) => {
    if (!req.auth || !roles.includes(req.auth.role)) {
      return res.status(403).json({ error: 'Insufficient role' })
    }

    return next()
  }
}

export function requirePrivilege(privilegeName) {
  return (req, res, next) => {
    const granted = Boolean(req.auth?.privileges?.[privilegeName])

    if (!granted && req.auth?.role !== 'admin') {
      return res.status(403).json({ error: 'Insufficient privilege' })
    }

    return next()
  }
}
