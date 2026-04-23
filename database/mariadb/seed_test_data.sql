-- Datos de prueba para Plataforma GIS Agrícola
-- Predios ficticios en región cañera (Veracruz/Tamaulipas)

-- Insertar predios de prueba
INSERT INTO properties (name, responsible, region, crop_type, is_sugarcane, planted_at, notes) VALUES
('Predio El Mirador', 'Juan García', 'Veracruz - Zona Centro', 'Caña de Azúcar', 1, '2023-01-15', 'Predio principal con riego tecnificado'),
('Predio Las Palmas', 'María López', 'Tamaulipas - Zona Sur', 'Caña de Azúcar', 1, '2023-06-20', 'Predio de producción alta, suelo fértil'),
('Predio San Fernando', 'Carlos Reyes', 'Veracruz - Zona Norte', 'Caña de Azúcar', 1, '2022-11-10', 'Predio en renovación de cultivo');

-- Obtener los IDs de los predios insertados (se asumen IDs 1, 2, 3)
-- Ahora insertar lotes para cada predio

-- PREDIO 1: El Mirador (3 lotes)
INSERT INTO lots (property_id, name, lot_classification_id, coordinates_geojson, area_hectares, notes) VALUES
(
  1,
  'Lote Norte - Soca 3 Años',
  2,
  '{"type":"Polygon","coordinates":[[[-97.25,21.50],[-97.24,21.50],[-97.24,21.51],[-97.25,21.51],[-97.25,21.50]]]}',
  15.5,
  'Caña soca con 3 años de corte, productividad media-alta'
),
(
  1,
  'Lote Central - Siembra Nueva',
  3,
  '{"type":"Polygon","coordinates":[[[-97.25,21.48],[-97.24,21.48],[-97.24,21.49],[-97.25,21.49],[-97.25,21.48]]]}',
  12.3,
  'Siembra nueva recién transplantada, crecimiento inicial'
),
(
  1,
  'Lote Sur - Área Productiva sin Caña',
  5,
  '{"type":"Polygon","coordinates":[[[-97.26,21.47],[-97.25,21.47],[-97.25,21.48],[-97.26,21.48],[-97.26,21.47]]]}',
  8.7,
  'Área en descanso de cultivo, rotación de suelo'
);

-- PREDIO 2: Las Palmas (2 lotes)
INSERT INTO lots (property_id, name, lot_classification_id, coordinates_geojson, area_hectares, notes) VALUES
(
  2,
  'Lote Poniente - Soca Vieja 6 Años',
  4,
  '{"type":"Polygon","coordinates":[[[-97.40,22.20],[-97.39,22.20],[-97.39,22.22],[-97.40,22.22],[-97.40,22.20]]]}',
  22.1,
  'Caña con 6 años de soca, productividad decreciente, próximo a renovar'
),
(
  2,
  'Lote Oriente - Siembra Nueva',
  3,
  '{"type":"Polygon","coordinates":[[[-97.38,22.20],[-97.37,22.20],[-97.37,22.21],[-97.38,22.21],[-97.38,22.20]]]}',
  18.9,
  'Siembra nueva parte del plan de renovación 2026'
);

-- PREDIO 3: San Fernando (4 lotes)
INSERT INTO lots (property_id, name, lot_classification_id, coordinates_geojson, area_hectares, notes) VALUES
(
  3,
  'Lote A - Soca 3 Años',
  2,
  '{"type":"Polygon","coordinates":[[[-97.15,21.80],[-97.14,21.80],[-97.14,21.82],[-97.15,21.82],[-97.15,21.80]]]}',
  19.2,
  'Productividad buena, mantenimiento regular'
),
(
  3,
  'Lote B - Descanso',
  6,
  '{"type":"Polygon","coordinates":[[[-97.14,21.80],[-97.13,21.80],[-97.13,21.82],[-97.14,21.82],[-97.14,21.80]]]}',
  10.5,
  'Lote en descanso de 1 año, preparación para siembra'
),
(
  3,
  'Lote C - No Productivo',
  7,
  '{"type":"Polygon","coordinates":[[[-97.13,21.80],[-97.12,21.80],[-97.12,21.81],[-97.13,21.81],[-97.13,21.80]]]}',
  5.2,
  'Área de uso no agrícola: caminos y servicios'
),
(
  3,
  'Lote D - Siembra Nueva',
  3,
  '{"type":"Polygon","coordinates":[[[-97.15,21.78],[-97.14,21.78],[-97.14,21.79],[-97.15,21.79],[-97.15,21.78]]]}',
  14.8,
  'Siembra nueva reciente con expectativa de productividad alta'
);
