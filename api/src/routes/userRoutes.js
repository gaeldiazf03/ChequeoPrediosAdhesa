import { Router } from 'express'
import bcrypt from 'bcryptjs'
import { pool } from '../db.js'
import { requireAuth, requireRole } from '../middleware/auth.js'

export const userRoutes = Router()

userRoutes.use(requireAuth)
userRoutes.use(requireRole('admin'))

userRoutes.get('/', async (_req, res) => {
  try {
    const [rows] = await pool.query(
      `
      SELECT id, name, username, email, role, active, created_at, updated_at
      FROM users
      ORDER BY created_at DESC
      `,
    )

    return res.json({
      users: rows.map((row) => ({
        id: String(row.id),
        name: row.name,
        username: row.username,
        email: row.email ?? null,
        role: row.role,
        active: Boolean(row.active),
        createdAt: row.created_at,
        updatedAt: row.updated_at,
      })),
    })
  } catch (error) {
    console.error('GET /users failed', error)
    return res.status(500).json({ error: 'Internal server error' })
  }
})

userRoutes.post('/', async (req, res) => {
  const username = String(req.body?.username ?? '').trim().toLowerCase()
  const password = String(req.body?.password ?? '')
  const name = String(req.body?.name ?? '').trim()
  const emailRaw = String(req.body?.email ?? '').trim()
  const email = emailRaw ? emailRaw.toLowerCase() : null
  const role = String(req.body?.role ?? 'viewer')

  if (!username || !password || !name) {
    return res.status(400).json({ error: 'name, username and password are required' })
  }

  if (!['admin', 'manager', 'viewer'].includes(role)) {
    return res.status(400).json({ error: 'invalid role' })
  }

  const privilegeDefaultsByRole = {
    admin: {
      canEditResponsibles: 1,
      canEditNodes: 1,
      canRegisterWatering: 1,
      canEditPlantingDate: 1,
      canEditCropType: 1,
      canEditPropertyName: 1,
    },
    manager: {
      canEditResponsibles: 1,
      canEditNodes: 1,
      canRegisterWatering: 1,
      canEditPlantingDate: 1,
      canEditCropType: 1,
      canEditPropertyName: 1,
    },
    viewer: {
      canEditResponsibles: 0,
      canEditNodes: 0,
      canRegisterWatering: 0,
      canEditPlantingDate: 0,
      canEditCropType: 0,
      canEditPropertyName: 0,
    },
  }

  const connection = await pool.getConnection()

  try {
    const passwordHash = await bcrypt.hash(password, 12)

    await connection.beginTransaction()

    const [insertUserResult] = await connection.query(
      `
      INSERT INTO users (name, username, email, password_hash, role, active)
      VALUES (?, ?, ?, ?, ?, 1)
      `,
      [name, username, email, passwordHash, role],
    )

    const userId = insertUserResult.insertId
    const defaults = privilegeDefaultsByRole[role]

    await connection.query(
      `
      INSERT INTO user_privileges (
        user_id,
        can_edit_responsibles,
        can_edit_nodes,
        can_register_watering,
        can_edit_planting_date,
        can_edit_crop_type,
        can_edit_property_name
      )
      VALUES (?, ?, ?, ?, ?, ?, ?)
      `,
      [
        userId,
        defaults.canEditResponsibles,
        defaults.canEditNodes,
        defaults.canRegisterWatering,
        defaults.canEditPlantingDate,
        defaults.canEditCropType,
        defaults.canEditPropertyName,
      ],
    )

    await connection.commit()

    return res.status(201).json({
      user: {
        id: String(userId),
        name,
        username,
        email,
        role,
        active: true,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      },
    })
  } catch (error) {
    await connection.rollback()

    if (error.code === 'ER_DUP_ENTRY') {
      return res.status(409).json({ error: 'username or email already exists' })
    }

    console.error('POST /users failed', error)
    return res.status(500).json({ error: 'Internal server error' })
  } finally {
    connection.release()
  }
})
