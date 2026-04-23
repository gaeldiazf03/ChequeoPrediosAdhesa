import bcrypt from 'bcryptjs'
import jwt from 'jsonwebtoken'
import { pool } from '../db.js'
import { config } from '../config.js'

function mapPrivilegeRow(row) {
  if (!row) {
    return {
      canEditResponsibles: false,
      canEditNodes: false,
      canRegisterWatering: false,
      canEditPlantingDate: false,
      canEditCropType: false,
      canEditPropertyName: false,
    }
  }

  return {
    canEditResponsibles: Boolean(row.can_edit_responsibles),
    canEditNodes: Boolean(row.can_edit_nodes),
    canRegisterWatering: Boolean(row.can_register_watering),
    canEditPlantingDate: Boolean(row.can_edit_planting_date),
    canEditCropType: Boolean(row.can_edit_crop_type),
    canEditPropertyName: Boolean(row.can_edit_property_name),
  }
}

export async function loginWithPassword(username, password) {
  const [rows] = await pool.query(
    `
      SELECT
        u.id,
        u.name,
        u.username,
        u.email,
        u.password_hash,
        u.role,
        u.active,
        p.can_edit_responsibles,
        p.can_edit_nodes,
        p.can_register_watering,
        p.can_edit_planting_date,
        p.can_edit_crop_type,
        p.can_edit_property_name
      FROM users u
      LEFT JOIN user_privileges p ON p.user_id = u.id
      WHERE u.username = ?
      LIMIT 1
    `,
    [username],
  )

  const user = rows[0]

  if (!user) {
    return null
  }

  const validPassword = await bcrypt.compare(password, user.password_hash)

  if (!validPassword || !user.active) {
    return null
  }

  const privileges = mapPrivilegeRow(user)

  const session = {
    id: String(user.id),
    name: user.name,
    username: user.username,
    email: user.email ?? null,
    role: user.role,
    active: Boolean(user.active),
    privileges,
  }

  const token = jwt.sign(
    {
      sub: String(user.id),
      role: user.role,
      privileges,
    },
    config.jwtSecret,
    { expiresIn: '8h' },
  )

  return { session, token }
}
