import { Router } from 'express'
import { loginWithPassword } from '../services/authService.js'

export const authRoutes = Router()

authRoutes.post('/login', async (req, res) => {
  try {
    const username = String(req.body?.username ?? '').trim().toLowerCase()
    const password = String(req.body?.password ?? '')

    if (!username || !password) {
      return res.status(400).json({ error: 'Username and password are required' })
    }

    const result = await loginWithPassword(username, password)

    if (!result) {
      return res.status(401).json({ error: 'Invalid credentials' })
    }

    return res.json(result)
  } catch (error) {
    console.error('POST /auth/login failed', error)
    return res.status(500).json({ error: 'Internal server error' })
  }
})
