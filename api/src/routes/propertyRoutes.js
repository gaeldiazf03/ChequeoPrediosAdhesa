import { Router } from 'express'
import multer from 'multer'
import { DOMParser } from '@xmldom/xmldom'
import { kml as toGeoJsonKml } from '@tmcw/togeojson'
import { pool } from '../db.js'
import { requireAuth, requireRole } from '../middleware/auth.js'

export const propertyRoutes = Router()

const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 5 * 1024 * 1024 },
})

function parsePolygonNodesFromKml(kmlText) {
  const xmlDocument = new DOMParser().parseFromString(kmlText, 'text/xml')
  const featureCollection = toGeoJsonKml(xmlDocument)
  const polygons = []

  for (const feature of featureCollection.features ?? []) {
    if (!feature?.geometry) {
      continue
    }

    const propertyName = String(feature.properties?.name ?? '').trim()

    if (feature.geometry.type === 'Polygon') {
      polygons.push({
        name: propertyName,
        ring: feature.geometry.coordinates?.[0] ?? [],
      })
      continue
    }

    if (feature.geometry.type === 'MultiPolygon') {
      for (const polygon of feature.geometry.coordinates ?? []) {
        polygons.push({
          name: propertyName,
          ring: polygon?.[0] ?? [],
        })
      }
    }
  }

  return polygons
}

function normalizeRingToNodes(ring) {
  const points = []

  for (const coordinate of ring ?? []) {
    const lng = Number(coordinate?.[0])
    const lat = Number(coordinate?.[1])

    if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
      continue
    }

    points.push({ lat, lng })
  }

  if (points.length >= 2) {
    const first = points[0]
    const last = points[points.length - 1]

    if (first.lat === last.lat && first.lng === last.lng) {
      points.pop()
    }
  }

  return points
}

propertyRoutes.use(requireAuth)

propertyRoutes.get('/', async (_req, res) => {
  try {
    const [properties] = await pool.query(
      `
      SELECT
        id,
        name,
        responsible,
        region,
        crop_type,
        is_sugarcane,
        planted_at,
        last_watered_at,
        watering_frequency_per_month,
        notes
      FROM properties
      ORDER BY name ASC
      `,
    )

    const [nodes] = await pool.query(
      `
      SELECT property_id, node_order, latitude, longitude
      FROM property_nodes
      ORDER BY property_id ASC, node_order ASC
      `,
    )

    const [lots] = await pool.query(
      `
      SELECT
        l.id,
        l.property_id,
        l.name,
        l.classification_id,
        l.responsible,
        l.area_hectares,
        l.coordinates_geojson,
        l.notes,
        l.action_plan,
        lc.code,
        lc.name AS classification_name,
        lc.color_hex
      FROM lots l
      LEFT JOIN lot_classifications lc ON lc.id = l.classification_id
      ORDER BY l.property_id ASC, l.name ASC
      `,
    )

    const nodesByProperty = new Map()
    const lotsByProperty = new Map()

    for (const node of nodes) {
      const key = String(node.property_id)
      const current = nodesByProperty.get(key) ?? []

      current.push({
        lat: Number(node.latitude),
        lng: Number(node.longitude),
      })

      nodesByProperty.set(key, current)
    }

    for (const lot of lots) {
      const key = String(lot.property_id)
      const current = lotsByProperty.get(key) ?? []

      current.push({
        id: String(lot.id),
        name: lot.name,
        classificationId: Number(lot.classification_id),
        classificationCode: lot.code,
        classificationName: lot.classification_name,
        colorHex: lot.color_hex,
        responsible: lot.responsible ?? '',
        areaHectares: lot.area_hectares ? Number(lot.area_hectares) : null,
        coordinatesGeojson: lot.coordinates_geojson ? JSON.parse(lot.coordinates_geojson) : null,
        notes: lot.notes ?? '',
        actionPlan: lot.action_plan ?? '',
      })

      lotsByProperty.set(key, current)
    }

    const payload = properties.map((property) => ({
      id: String(property.id),
      name: property.name,
      responsible: property.responsible,
      region: property.region,
      cropType: property.crop_type,
      isSugarcane: Boolean(property.is_sugarcane),
      plantedAt: property.planted_at,
      lastWateredAt: property.last_watered_at,
      wateringFrequencyPerMonth: Number(property.watering_frequency_per_month ?? 0),
      notes: property.notes ?? '',
      nodes: nodesByProperty.get(String(property.id)) ?? [],
      lots: lotsByProperty.get(String(property.id)) ?? [],
    }))

    return res.json({ properties: payload })
  } catch (error) {
    console.error('GET /properties failed', error)
    return res.status(500).json({ error: 'Internal server error' })
  }
})

propertyRoutes.post('/', requireRole('admin'), async (req, res) => {
  const {
    name,
    responsible,
    region,
    cropType,
    isSugarcane,
    plantedAt,
    wateringFrequencyPerMonth,
    notes,
  } = req.body ?? {}

  if (!name) {
    return res.status(400).json({ error: 'name is required' })
  }

  try {
    const [insertResult] = await pool.query(
      `
      INSERT INTO properties (
        name,
        responsible,
        region,
        crop_type,
        is_sugarcane,
        planted_at,
        watering_frequency_per_month,
        notes,
        created_by
      )
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
      `,
      [
        name,
        responsible ?? '',
        region ?? '',
        cropType ?? '',
        isSugarcane ? 1 : 0,
        plantedAt || null,
        Number(wateringFrequencyPerMonth ?? 0),
        notes ?? '',
        Number(req.auth.sub),
      ],
    )

    const propertyId = insertResult.insertId

    return res.status(201).json({
      property: {
        id: String(propertyId),
        name,
        responsible: responsible ?? '',
        region: region ?? '',
        cropType: cropType ?? '',
        isSugarcane: Boolean(isSugarcane),
        plantedAt: plantedAt ?? null,
        lastWateredAt: null,
        wateringFrequencyPerMonth: Number(wateringFrequencyPerMonth ?? 0),
        notes: notes ?? '',
        nodes: [],
        lots: [],
      },
    })
  } catch (error) {
    console.error('POST /properties failed', error)
    return res.status(500).json({ error: 'Internal server error' })
  }
})

propertyRoutes.post(
  '/import/kml',
  requireRole('admin'),
  upload.single('kmlFile'),
  async (req, res) => {
    const responsible = String(req.body?.responsible ?? '').trim() || 'Sin asignar'
    const region = String(req.body?.region ?? '').trim() || 'Sin región'
    const fileBuffer = req.file?.buffer

    if (!fileBuffer) {
      return res.status(400).json({ error: 'kmlFile is required' })
    }

    let polygons

    try {
      polygons = parsePolygonNodesFromKml(fileBuffer.toString('utf8'))
    } catch (error) {
      console.error('KML parse failed', error)
      return res.status(400).json({ error: 'Invalid KML file' })
    }

    if (polygons.length === 0) {
      return res.status(400).json({ error: 'No polygon geometries were found in the KML' })
    }

    const connection = await pool.getConnection()
    const imported = []
    let skipped = 0

    try {
      await connection.beginTransaction()

      for (let index = 0; index < polygons.length; index += 1) {
        const polygon = polygons[index]
        const nodes = normalizeRingToNodes(polygon.ring)

        if (nodes.length < 3) {
          skipped += 1
          continue
        }

        const propertyName = polygon.name || `Predio importado ${index + 1}`
        const [insertResult] = await connection.query(
          `
          INSERT INTO properties (
            name,
            responsible,
            region,
            crop_type,
            is_sugarcane,
            watering_frequency_per_month,
            created_by
          )
          VALUES (?, ?, ?, ?, ?, ?, ?)
          `,
          [
            propertyName,
            responsible,
            region,
            'Caña de Azúcar',
            1,
            0,
            Number(req.auth.sub),
          ],
        )

        const propertyId = Number(insertResult.insertId)

        for (let nodeOrder = 0; nodeOrder < nodes.length; nodeOrder += 1) {
          const node = nodes[nodeOrder]

          await connection.query(
            `
            INSERT INTO property_nodes (property_id, node_order, latitude, longitude)
            VALUES (?, ?, ?, ?)
            `,
            [propertyId, nodeOrder, node.lat, node.lng],
          )
        }

        imported.push({
          id: String(propertyId),
          name: propertyName,
          nodesCount: nodes.length,
        })
      }

      await connection.commit()

      return res.status(201).json({
        imported,
        importedCount: imported.length,
        skipped,
      })
    } catch (error) {
      await connection.rollback()
      console.error('POST /properties/import/kml failed', error)
      return res.status(500).json({ error: 'Internal server error' })
    } finally {
      connection.release()
    }
  },
)

propertyRoutes.put('/:propertyId', requireRole('admin'), async (req, res) => {
  const { propertyId } = req.params
  const body = req.body ?? {}

  try {
    const [rows] = await pool.query(
      `
      SELECT
        id,
        name,
        responsible,
        crop_type,
        is_sugarcane,
        planted_at,
        last_watered_at,
        watering_frequency_per_month,
        notes
      FROM properties
      WHERE id = ?
      LIMIT 1
      `,
      [Number(propertyId)],
    )

    const current = rows?.[0]

    if (!current) {
      return res.status(404).json({ error: 'Property not found' })
    }

    const has = (key) => Object.prototype.hasOwnProperty.call(body, key)

    const nextName = has('name') ? body.name : current.name
    const nextResponsible = has('responsible') ? body.responsible : current.responsible
    const nextCropType = has('cropType') ? body.cropType : current.crop_type
    const nextIsSugarcane = has('isSugarcane')
      ? (body.isSugarcane ? 1 : 0)
      : current.is_sugarcane
    const nextPlantedAt = has('plantedAt') ? body.plantedAt || null : current.planted_at
    const nextLastWateredAt = has('lastWateredAt')
      ? body.lastWateredAt || null
      : current.last_watered_at
    const nextWateringFrequencyPerMonth = has('wateringFrequencyPerMonth')
      ? Number(body.wateringFrequencyPerMonth ?? 0)
      : Number(current.watering_frequency_per_month ?? 0)
    const nextNotes = has('notes') ? (body.notes ?? '') : (current.notes ?? '')

    await pool.query(
      `
      UPDATE properties
      SET
        name = ?,
        responsible = ?,
        crop_type = ?,
        is_sugarcane = ?,
        planted_at = ?,
        last_watered_at = ?,
        watering_frequency_per_month = ?,
        notes = ?,
        updated_by = ?
      WHERE id = ?
      `,
      [
        nextName,
        nextResponsible,
        nextCropType,
        nextIsSugarcane,
        nextPlantedAt,
        nextLastWateredAt,
        nextWateringFrequencyPerMonth,
        nextNotes,
        Number(req.auth.sub),
        Number(propertyId),
      ],
    )

    return res.json({ ok: true })
  } catch (error) {
    console.error('PUT /properties/:propertyId failed', error)
    return res.status(500).json({ error: 'Internal server error' })
  }
})

propertyRoutes.put('/:propertyId/nodes', requireRole('admin'), async (req, res) => {
  const { propertyId } = req.params
  const { nodes } = req.body ?? {}

  if (!Array.isArray(nodes) || nodes.length < 3) {
    return res.status(400).json({ error: 'At least 3 nodes are required' })
  }

  const connection = await pool.getConnection()

  try {
    await connection.beginTransaction()

    await connection.query('DELETE FROM property_nodes WHERE property_id = ?', [
      Number(propertyId),
    ])

    for (let index = 0; index < nodes.length; index += 1) {
      const node = nodes[index]

      await connection.query(
        `
        INSERT INTO property_nodes (property_id, node_order, latitude, longitude)
        VALUES (?, ?, ?, ?)
        `,
        [Number(propertyId), index, Number(node.lat), Number(node.lng)],
      )
    }

    await connection.query('UPDATE properties SET updated_by = ? WHERE id = ?', [
      Number(req.auth.sub),
      Number(propertyId),
    ])

    await connection.commit()

    return res.json({ ok: true })
  } catch (error) {
    await connection.rollback()
    console.error('PUT /properties/:propertyId/nodes failed', error)
    return res.status(500).json({ error: 'Internal server error' })
  } finally {
    connection.release()
  }
})

propertyRoutes.post('/:propertyId/watering', requireRole('admin'), async (req, res) => {
  const { propertyId } = req.params
  const wateredAt = String(req.body?.wateredAt ?? '')

  if (!wateredAt) {
    return res.status(400).json({ error: 'wateredAt is required' })
  }

  try {
    await pool.query(
      `
      INSERT INTO watering_logs (property_id, watered_at, created_by, notes)
      VALUES (?, ?, ?, ?)
      `,
      [
        Number(propertyId),
        wateredAt,
        Number(req.auth.sub),
        String(req.body?.notes ?? ''),
      ],
    )

    await pool.query(
      'UPDATE properties SET last_watered_at = ?, updated_by = ? WHERE id = ?',
      [wateredAt.slice(0, 10), Number(req.auth.sub), Number(propertyId)],
    )

    return res.json({ ok: true })
  } catch (error) {
    console.error('POST /properties/:propertyId/watering failed', error)
    return res.status(500).json({ error: 'Internal server error' })
  }
})

propertyRoutes.delete('/:propertyId', requireRole('admin'), async (req, res) => {
  const { propertyId } = req.params

  try {
    await pool.query('DELETE FROM properties WHERE id = ?', [Number(propertyId)])

    return res.json({ ok: true })
  } catch (error) {
    console.error('DELETE /properties/:propertyId failed', error)
    return res.status(500).json({ error: 'Internal server error' })
  }
})
