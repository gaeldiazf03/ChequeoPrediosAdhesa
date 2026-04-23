import { Router } from 'express'
import { pool } from '../db.js'
import { requireAuth, requireRole } from '../middleware/auth.js'

export const lotRoutes = Router()

lotRoutes.use(requireAuth)

lotRoutes.get('/classifications', async (_req, res) => {
  try {
    const [classifications] = await pool.query(
      `
      SELECT id, code, name, description, color_hex
      FROM lot_classifications
      ORDER BY id ASC
      `,
    )

    return res.json({
      classifications: classifications.map((row) => ({
        id: Number(row.id),
        code: row.code,
        name: row.name,
        description: row.description ?? '',
        colorHex: row.color_hex,
      })),
    })
  } catch (error) {
    console.error('GET /lots/classifications failed', error)
    return res.status(500).json({ error: 'Internal server error' })
  }
})

lotRoutes.get('/:propertyId', async (req, res) => {
  const { propertyId } = req.params

  try {
    const [lots] = await pool.query(
      `
      SELECT
        l.id,
        l.name,
        l.classification_id,
        l.responsible,
        l.area_hectares,
        l.coordinates_geojson,
        l.notes,
        l.action_plan,
        lc.code,
        lc.name as classification_name,
        lc.color_hex,
        l.created_at,
        l.updated_at
      FROM lots l
      LEFT JOIN lot_classifications lc ON lc.id = l.classification_id
      WHERE l.property_id = ?
      ORDER BY l.name ASC
      `,
      [Number(propertyId)],
    )

    return res.json({
      lots: lots.map((row) => ({
        id: String(row.id),
        name: row.name,
        classificationId: Number(row.classification_id),
        classificationCode: row.code,
        classificationName: row.classification_name,
        colorHex: row.color_hex,
        responsible: row.responsible ?? '',
        areaHectares: row.area_hectares ? Number(row.area_hectares) : null,
        coordinatesGeojson: row.coordinates_geojson
          ? JSON.parse(row.coordinates_geojson)
          : null,
        notes: row.notes ?? '',
        actionPlan: row.action_plan ?? '',
        createdAt: row.created_at,
        updatedAt: row.updated_at,
      })),
    })
  } catch (error) {
    console.error('GET /lots/:propertyId failed', error)
    return res.status(500).json({ error: 'Internal server error' })
  }
})

lotRoutes.post('/', requireRole('admin'), async (req, res) => {
  const {
    propertyId,
    name,
    classificationId,
    responsible,
    areaHectares,
    coordinatesGeojson,
    notes,
    actionPlan,
  } = req.body ?? {}

  if (!propertyId || !name) {
    return res
      .status(400)
      .json({ error: 'propertyId and name are required' })
  }

  try {
    let resolvedClassificationId = classificationId ? Number(classificationId) : 0

    if (!resolvedClassificationId) {
      const [classificationRows] = await pool.query(
        `
        SELECT id
        FROM lot_classifications
        ORDER BY id ASC
        LIMIT 1
        `,
      )

      resolvedClassificationId = Number(classificationRows?.[0]?.id ?? 0)
    }

    if (!resolvedClassificationId) {
      return res.status(400).json({
        error: 'No existe un tipo interno para crear lotes. Registra uno en lot_classifications.',
      })
    }

    const [insertResult] = await pool.query(
      `
      INSERT INTO lots (
        property_id,
        name,
        classification_id,
        responsible,
        area_hectares,
        coordinates_geojson,
        notes,
        action_plan,
        created_by
      )
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
      `,
      [
        Number(propertyId),
        name,
        resolvedClassificationId,
        responsible ?? '',
        areaHectares ? Number(areaHectares) : null,
        coordinatesGeojson ? JSON.stringify(coordinatesGeojson) : null,
        notes ?? '',
        actionPlan ?? '',
        Number(req.auth.sub),
      ],
    )

    const lotId = insertResult.insertId

    return res.status(201).json({
      lot: {
        id: String(lotId),
        name,
        classificationId: resolvedClassificationId,
        responsible: responsible ?? '',
        areaHectares: areaHectares ? Number(areaHectares) : null,
        coordinatesGeojson,
        notes: notes ?? '',
        actionPlan: actionPlan ?? '',
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      },
    })
  } catch (error) {
    console.error('POST /lots failed', error)
    return res.status(500).json({ error: 'Internal server error' })
  }
})

lotRoutes.put('/:lotId', requireRole('admin'), async (req, res) => {
  const { lotId } = req.params
  const body = req.body ?? {}

  try {
    const [rows] = await pool.query(
      `
      SELECT
        id,
        name,
        classification_id,
        responsible,
        area_hectares,
        coordinates_geojson,
        notes,
        action_plan
      FROM lots
      WHERE id = ?
      LIMIT 1
      `,
      [Number(lotId)],
    )

    const current = rows?.[0]

    if (!current) {
      return res.status(404).json({ error: 'Lot not found' })
    }

    const has = (key) => Object.prototype.hasOwnProperty.call(body, key)

    const nextName = has('name') ? body.name : current.name
    const nextClassificationId = has('classificationId')
      ? Number(body.classificationId)
      : Number(current.classification_id)
    const nextResponsible = has('responsible') ? body.responsible ?? '' : current.responsible ?? ''
    const nextAreaHectares = has('areaHectares')
      ? body.areaHectares
        ? Number(body.areaHectares)
        : null
      : current.area_hectares
    const nextCoordinatesGeojson = has('coordinatesGeojson')
      ? body.coordinatesGeojson
        ? JSON.stringify(body.coordinatesGeojson)
        : null
      : current.coordinates_geojson
    const nextNotes = has('notes') ? body.notes ?? '' : current.notes ?? ''
    const nextActionPlan = has('actionPlan') ? body.actionPlan ?? '' : current.action_plan ?? ''

    if (!nextName || !nextClassificationId) {
      return res.status(400).json({ error: 'name and classificationId are required' })
    }

    await pool.query(
      `
      UPDATE lots
      SET
        name = ?,
        classification_id = ?,
        responsible = ?,
        area_hectares = ?,
        coordinates_geojson = ?,
        notes = ?,
        action_plan = ?,
        updated_by = ?
      WHERE id = ?
      `,
      [
        nextName,
        nextClassificationId,
        nextResponsible,
        nextAreaHectares,
        nextCoordinatesGeojson,
        nextNotes,
        nextActionPlan,
        Number(req.auth.sub),
        Number(lotId),
      ],
    )

    return res.json({ ok: true })
  } catch (error) {
    console.error('PUT /lots/:lotId failed', error)
    return res.status(500).json({ error: 'Internal server error' })
  }
})

lotRoutes.delete('/:lotId', requireRole('admin'), async (req, res) => {
  const { lotId } = req.params

  try {
    await pool.query('DELETE FROM lots WHERE id = ?', [Number(lotId)])

    return res.json({ ok: true })
  } catch (error) {
    console.error('DELETE /lots/:lotId failed', error)
    return res.status(500).json({ error: 'Internal server error' })
  }
})
