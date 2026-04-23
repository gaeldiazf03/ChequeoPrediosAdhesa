CREATE DATABASE IF NOT EXISTS chequeo_predios
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE chequeo_predios;

CREATE TABLE users (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  name VARCHAR(120) NOT NULL,
  username VARCHAR(80) NOT NULL,
  email VARCHAR(180) NULL,
  password_hash VARCHAR(255) NOT NULL,
  role ENUM('admin', 'manager', 'viewer') NOT NULL DEFAULT 'viewer',
  active TINYINT(1) NOT NULL DEFAULT 1,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_users_username (username),
  UNIQUE KEY uq_users_email (email)
);

CREATE TABLE user_privileges (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id BIGINT UNSIGNED NOT NULL,
  can_edit_responsibles TINYINT(1) NOT NULL DEFAULT 0,
  can_edit_nodes TINYINT(1) NOT NULL DEFAULT 0,
  can_register_watering TINYINT(1) NOT NULL DEFAULT 0,
  can_edit_planting_date TINYINT(1) NOT NULL DEFAULT 0,
  can_edit_crop_type TINYINT(1) NOT NULL DEFAULT 0,
  can_edit_property_name TINYINT(1) NOT NULL DEFAULT 0,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_user_privileges_user_id (user_id),
  CONSTRAINT fk_user_privileges_user_id
    FOREIGN KEY (user_id) REFERENCES users (id)
    ON DELETE CASCADE
);

CREATE TABLE properties (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  name VARCHAR(180) NOT NULL,
  responsible VARCHAR(180) NOT NULL DEFAULT '',
  region VARCHAR(180) NOT NULL DEFAULT '',
  crop_type VARCHAR(100) NOT NULL DEFAULT '',
  is_sugarcane TINYINT(1) NOT NULL DEFAULT 0,
  planted_at DATE NULL,
  last_watered_at DATE NULL,
  watering_frequency_per_month INT NOT NULL DEFAULT 0,
  notes TEXT NULL,
  created_by BIGINT UNSIGNED NULL,
  updated_by BIGINT UNSIGNED NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_properties_name (name),
  KEY idx_properties_region (region),
  CONSTRAINT fk_properties_created_by
    FOREIGN KEY (created_by) REFERENCES users (id)
    ON DELETE SET NULL,
  CONSTRAINT fk_properties_updated_by
    FOREIGN KEY (updated_by) REFERENCES users (id)
    ON DELETE SET NULL
);

CREATE TABLE property_nodes (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  property_id BIGINT UNSIGNED NOT NULL,
  node_order INT NOT NULL,
  latitude DECIMAL(10, 7) NOT NULL,
  longitude DECIMAL(10, 7) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_property_nodes_position (property_id, node_order),
  KEY idx_property_nodes_property_id (property_id),
  CONSTRAINT fk_property_nodes_property_id
    FOREIGN KEY (property_id) REFERENCES properties (id)
    ON DELETE CASCADE
);

CREATE TABLE lot_classifications (
  id TINYINT UNSIGNED NOT NULL,
  code VARCHAR(50) NOT NULL,
  name VARCHAR(120) NOT NULL,
  description TEXT NULL,
  color_hex VARCHAR(7) NOT NULL DEFAULT '#cccccc',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_lot_classifications_code (code)
);

INSERT INTO lot_classifications (id, code, name, description, color_hex) VALUES
  (1, 'sugarcane_new', 'Siembra Nueva', 'Caña plantada en ciclo actual', '#2ecc71'),
  (2, 'sugarcane_soca_3y', 'Caña Soca 3 Años', 'Caña de primer rebrote (máximo 3 años desde siembra)', '#27ae60'),
  (3, 'sugarcane_soca_6y', 'Caña Soca Vieja 6 Años', 'Caña de rebrote avanzado (6 años o más desde siembra)', '#229954'),
  (4, 'sugarcane_soca_old', 'Caña Soca Obsoleta', 'Caña en fin de ciclo, próxima a erradicación', '#1e5631'),
  (5, 'productive_no_sugarcane', 'Área Productiva Sin Caña', 'Terreno cultivado con otros cultivos', '#f39c12'),
  (6, 'fallow', 'Descanso/Barbecho', 'Terreno en descanso o preparación', '#e8daef'),
  (7, 'non_productive', 'Área No Productiva', 'Accesos, caminos, zona de infraestructura', '#95a5a6');

CREATE TABLE lots (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  property_id BIGINT UNSIGNED NOT NULL,
  name VARCHAR(120) NOT NULL,
  classification_id TINYINT UNSIGNED NOT NULL,
  responsible VARCHAR(180) NOT NULL DEFAULT '',
  area_hectares DECIMAL(10, 3) NULL,
  coordinates_geojson JSON NULL,
  notes VARCHAR(500) NULL,
  action_plan TEXT NULL,
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
);

CREATE TABLE watering_logs (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  property_id BIGINT UNSIGNED NOT NULL,
  watered_at DATETIME NOT NULL,
  notes VARCHAR(255) NULL,
  created_by BIGINT UNSIGNED NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_watering_logs_property_id (property_id),
  CONSTRAINT fk_watering_logs_property_id
    FOREIGN KEY (property_id) REFERENCES properties (id)
    ON DELETE CASCADE,
  CONSTRAINT fk_watering_logs_created_by
    FOREIGN KEY (created_by) REFERENCES users (id)
    ON DELETE SET NULL
);

CREATE INDEX idx_properties_crop_type ON properties (crop_type);
CREATE INDEX idx_properties_is_sugarcane ON properties (is_sugarcane);

-- Si ya tenias el esquema previo con login por email, aplica este ajuste de migracion:
-- ALTER TABLE users ADD COLUMN username VARCHAR(80) NOT NULL AFTER name;
-- UPDATE users SET username = LOWER(SUBSTRING_INDEX(email, '@', 1)) WHERE username = '';
-- ALTER TABLE users MODIFY email VARCHAR(180) NULL;
-- CREATE UNIQUE INDEX uq_users_username ON users (username);