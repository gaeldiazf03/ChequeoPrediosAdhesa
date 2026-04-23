import mysql from 'mysql2/promise.js'
import * as fs from 'fs'
import * as path from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

async function seedTestData() {
  let connection

  try {
    connection = await mysql.createConnection({
      host: process.env.DB_HOST || 'localhost',
      user: process.env.DB_USER || 'root',
      password: process.env.DB_PASSWORD || '',
      database: process.env.DB_NAME || 'chequeo_predios',
      multipleStatements: true,
    })

    console.log('Seeding test data...')

    // Leer el archivo SQL
    const sqlFilePath = path.join(__dirname, '../mariadb/seed_test_data.sql')
    const sqlContent = fs.readFileSync(sqlFilePath, 'utf8')

    // Ejecutar las sentencias SQL
    await connection.query(sqlContent)

    console.log('✓ Test data seeded successfully')
    console.log('Properties and lots are now available in the database')
  } catch (error) {
    console.error('seed failed', error)
    process.exit(1)
  } finally {
    if (connection) {
      await connection.end()
    }
  }
}

seedTestData()
