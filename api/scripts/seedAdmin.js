import bcrypt from 'bcryptjs'
import dotenv from 'dotenv'
import mysql from 'mysql2/promise'

dotenv.config()

const db = {
  host: process.env.DB_HOST ?? '127.0.0.1',
  port: Number(process.env.DB_PORT ?? 3306),
  user: process.env.DB_USER ?? 'root',
  password: process.env.DB_PASSWORD ?? '',
  database: process.env.DB_NAME ?? 'chequeo_predios',
}

const adminUsername = process.env.ADMIN_USERNAME ?? 'admin'
const adminEmail = process.env.ADMIN_EMAIL || null
const adminName = process.env.ADMIN_NAME ?? 'Administrador principal'
const adminPassword =
  process.env.ADMIN_PASSWORD ?? 'EntrarAAdhesa_AhoraMismo!2026'

async function run() {
  const connection = await mysql.createConnection(db)

  try {
    const passwordHash = await bcrypt.hash(adminPassword, 12)

    const [existingRows] = await connection.query(
      'SELECT id FROM users WHERE username = ? LIMIT 1',
      [adminUsername],
    )

    let userId

    if (existingRows.length > 0) {
      userId = existingRows[0].id

      await connection.query(
        `
        UPDATE users
        SET name = ?, role = 'admin', active = 1, password_hash = ?, email = ?
        WHERE id = ?
        `,
        [adminName, passwordHash, adminEmail, userId],
      )
    } else {
      const [insertResult] = await connection.query(
        `
        INSERT INTO users (name, username, email, password_hash, role, active)
        VALUES (?, ?, ?, ?, 'admin', 1)
        `,
        [adminName, adminUsername, adminEmail, passwordHash],
      )

      userId = insertResult.insertId
    }

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
      VALUES (?, 1, 1, 1, 1, 1, 1)
      ON DUPLICATE KEY UPDATE
        can_edit_responsibles = VALUES(can_edit_responsibles),
        can_edit_nodes = VALUES(can_edit_nodes),
        can_register_watering = VALUES(can_register_watering),
        can_edit_planting_date = VALUES(can_edit_planting_date),
        can_edit_crop_type = VALUES(can_edit_crop_type),
        can_edit_property_name = VALUES(can_edit_property_name)
      `,
      [userId],
    )

    console.log(`Admin user ready: ${adminUsername}`)
  } finally {
    await connection.end()
  }
}

run().catch((error) => {
  console.error('seed:admin failed', error)
  process.exitCode = 1
})
