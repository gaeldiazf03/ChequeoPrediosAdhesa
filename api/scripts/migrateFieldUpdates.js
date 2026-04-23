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

async function columnExists(connection, tableName, columnName) {
  const [rows] = await connection.query(
    `
    SELECT COUNT(*) AS count
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = ?
      AND TABLE_NAME = ?
      AND COLUMN_NAME = ?
    `,
    [db.database, tableName, columnName],
  )

  return Number(rows[0]?.count ?? 0) > 0
}

async function run() {
  const connection = await mysql.createConnection(db)

  try {
    if (!(await columnExists(connection, 'properties', 'watering_frequency_per_month'))) {
      console.log('Adding properties.watering_frequency_per_month...')
      await connection.query(
        'ALTER TABLE properties ADD COLUMN watering_frequency_per_month INT NOT NULL DEFAULT 0 AFTER last_watered_at',
      )
    }

    if (!(await columnExists(connection, 'lots', 'responsible'))) {
      console.log('Adding lots.responsible...')
      await connection.query(
        "ALTER TABLE lots ADD COLUMN responsible VARCHAR(180) NOT NULL DEFAULT '' AFTER classification_id",
      )
    }

    if (!(await columnExists(connection, 'lots', 'action_plan'))) {
      console.log('Adding lots.action_plan...')
      await connection.query(
        'ALTER TABLE lots ADD COLUMN action_plan TEXT NULL AFTER notes',
      )
    }

    console.log('Field migration completed successfully')
  } finally {
    await connection.end()
  }
}

run().catch((error) => {
  console.error('field migration failed', error)
  process.exitCode = 1
})