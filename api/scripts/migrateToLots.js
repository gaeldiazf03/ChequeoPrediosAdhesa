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

async function run() {
  const connection = await mysql.createConnection(db)

  try {
    console.log('Creating lot_classifications table...')
    await connection.query(`
      CREATE TABLE IF NOT EXISTS lot_classifications (
        id TINYINT UNSIGNED NOT NULL,
        code VARCHAR(50) NOT NULL,
        name VARCHAR(120) NOT NULL,
        description TEXT NULL,
        color_hex VARCHAR(7) NOT NULL DEFAULT '#cccccc',
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (id),
        UNIQUE KEY uq_lot_classifications_code (code)
      )
    `)

    console.log('Inserting lot classifications...')
    await connection.query(`
      INSERT INTO lot_classifications (id, code, name, description, color_hex) VALUES
        (1, 'sugarcane_new', 'Siembra Nueva', 'Caña plantada en ciclo actual', '#2ecc71'),
        (2, 'sugarcane_soca_3y', 'Caña Soca 3 Años', 'Caña de primer rebrote (máximo 3 años desde siembra)', '#27ae60'),
        (3, 'sugarcane_soca_6y', 'Caña Soca Vieja 6 Años', 'Caña de rebrote avanzado (6 años o más desde siembra)', '#229954'),
        (4, 'sugarcane_soca_old', 'Caña Soca Obsoleta', 'Caña en fin de ciclo, próxima a erradicación', '#1e5631'),
        (5, 'productive_no_sugarcane', 'Área Productiva Sin Caña', 'Terreno cultivado con otros cultivos', '#f39c12'),
        (6, 'fallow', 'Descanso/Barbecho', 'Terreno en descanso o preparación', '#e8daef'),
        (7, 'non_productive', 'Área No Productiva', 'Accesos, caminos, zona de infraestructura', '#95a5a6')
      ON DUPLICATE KEY UPDATE
        code = VALUES(code),
        name = VALUES(name),
        description = VALUES(description),
        color_hex = VALUES(color_hex)
    `)

    console.log('Creating lots table...')
    await connection.query(`
      CREATE TABLE IF NOT EXISTS lots (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
        property_id BIGINT UNSIGNED NOT NULL,
        name VARCHAR(120) NOT NULL,
        classification_id TINYINT UNSIGNED NOT NULL,
        area_hectares DECIMAL(10, 3) NULL,
        coordinates_geojson JSON NULL,
        notes VARCHAR(500) NULL,
        created_by BIGINT UNSIGNED NULL,
        updated_by BIGINT UNSIGNED NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (id),
        KEY idx_lots_property_id (property_id),
        KEY idx_lots_classification_id (classification_id),
        CONSTRAINT fk_lots_property_id
          FOREIGN KEY (property_id) REFERENCES properties (id)
          ON DELETE CASCADE,
        CONSTRAINT fk_lots_classification_id
          FOREIGN KEY (classification_id) REFERENCES lot_classifications (id)
          ON DELETE RESTRICT
      )
    `)

    console.log('Migration completed successfully')
  } finally {
    await connection.end()
  }
}

run().catch((error) => {
  console.error('migration failed', error)
  process.exitCode = 1
})
