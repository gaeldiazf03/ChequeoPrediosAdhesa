import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import L from 'leaflet'
import { CircleMarker, MapContainer, Marker, Polygon, Popup, TileLayer, useMap, useMapEvents } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png'
import markerIcon from 'leaflet/dist/images/marker-icon.png'
import markerShadow from 'leaflet/dist/images/marker-shadow.png'
import './App.css'

type Role = 'admin' | 'manager' | 'viewer'

type AccountSummary = {
  id: string
  name: string
  username: string
  email: string | null
  role: Role
  active: boolean
}

type NodePoint = {
  lat: number
  lng: number
}

type LotClassification = {
  id: number
  code: string
  name: string
  description: string
  colorHex: string
}

type Lot = {
  id: string
  name: string
  classificationId: number
  classificationCode: string
  classificationName: string
  colorHex: string
  responsible: string
  areaHectares: number | null
  coordinatesGeojson: any
  notes: string
  actionPlan: string
}

type Property = {
  id: string
  name: string
  responsible: string
  region: string
  cropType: string
  isSugarcane: boolean
  plantedAt: string
  lastWateredAt: string
  wateringFrequencyPerMonth: number
  notes: string
  nodes: NodePoint[]
  lots: Lot[]
}

type DisplaySubpredio = {
  id: string
  title: string
  subtitle: string
  lotId: string | null
}

type ActionPlanItem = {
  id: string
  text: string
  done: boolean
}

type ThemeConfig = {
  colors: {
    background: string
    backgroundAlt: string
    surface: string
    surfaceAlt: string
    text: string
    muted: string
    border: string
    primary: string
    primarySoft: string
    success: string
    warning: string
    danger: string
  }
  typography: {
    heading: string
    body: string
    mono: string
  }
  fontSizes: {
    display: string
    title: string
    body: string
    small: string
  }
}

const MAP_CENTER: [number, number] = [21.4, -98.6]
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL as string | undefined
const PROPERTY_ORDER = ['Casa Blanca', 'Mango', 'Guzman', 'Paisabel', 'Isleta', 'Tamante']
const PROPERTY_ORDER_LOOKUP = new Set(PROPERTY_ORDER.map((name) => name.toLowerCase()))

const SUBPREDIOS_BY_PROPERTY: Record<string, string[]> = {
  'casa blanca': [],
  mango: ['terreno preparado hasta 2 rastra', 'preparado bordeado (siembra)'],
  guzman: [],
  paisabel: [],
  isleta: [
    'siembra nueva 2026',
    'caña 3 años',
    'inundación. sin cultivo',
    'caña rescatable 7 años',
    'caña rescatable 7 años',
    'caña rescatable 7 años',
    'caña rescatable 7 años',
    'caña rescatable siete años',
    'caña 3 años',
    'sin cultivo y en preparación',
    'sin cultivo y en preparación',
    'sin cultivo y en preparación',
  ],
  tamante: [
    'caña rescatable 5 años?',
    'caña rescatable 5 años?',
    'no productivo y area bombeo',
    'caña perdida',
  ],
}

function normalizeLabel(value: string) {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .trim()
}

function sortLotsForProperty(_propertyName: string, lots: Lot[]) {
  return [...lots]
}

function parseActionPlanItems(actionPlan: string): ActionPlanItem[] {
  if (!actionPlan?.trim()) {
    return []
  }

  try {
    const parsed = JSON.parse(actionPlan)

    if (Array.isArray(parsed)) {
      return parsed
        .map((item, index) => {
          if (typeof item === 'string') {
            return {
              id: `legacy-${index}`,
              text: item.trim(),
              done: false,
            }
          }

          return {
            id: String(item?.id ?? `item-${index}`),
            text: String(item?.text ?? '').trim(),
            done: Boolean(item?.done),
          }
        })
        .filter((item) => item.text)
    }
  } catch {
    // Fall back to plain text parsing for legacy action plans.
  }

  return actionPlan
    .split('\n')
    .map((line, index) => ({
      id: `line-${index}`,
      text: line.replace(/^[-*]\s*/, '').trim(),
      done: false,
    }))
    .filter((item) => item.text)
}

function serializeActionPlanItems(items: ActionPlanItem[]): string {
  const cleaned = items
    .map((item) => ({
      id: item.id,
      text: item.text.trim(),
      done: Boolean(item.done),
    }))
    .filter((item) => item.text)

  return JSON.stringify(cleaned)
}

function calculateNodeDistance(a: NodePoint, b: NodePoint) {
  const latDiff = a.lat - b.lat
  const lngDiff = a.lng - b.lng
  return Math.sqrt(latDiff * latDiff + lngDiff * lngDiff)
}

function orderNodesByClosestPair(nodes: NodePoint[]) {
  if (nodes.length <= 2) {
    return [...nodes]
  }

  const available = [...nodes]

  let leftmostIndex = 0
  for (let index = 1; index < available.length; index += 1) {
    if (available[index].lng < available[leftmostIndex].lng) {
      leftmostIndex = index
    }
  }

  const first = available.splice(leftmostIndex, 1)[0]

  let nearestToFirstIndex = 0
  for (let index = 1; index < available.length; index += 1) {
    if (calculateNodeDistance(first, available[index]) < calculateNodeDistance(first, available[nearestToFirstIndex])) {
      nearestToFirstIndex = index
    }
  }

  const second = available.splice(nearestToFirstIndex, 1)[0]
  const ordered = [first, second]

  while (available.length > 0) {
    const candidate = available.shift() as NodePoint

    let bestInsertAt = 1
    let bestScore = Number.POSITIVE_INFINITY

    for (let index = 0; index < ordered.length; index += 1) {
      const current = ordered[index]
      const next = ordered[(index + 1) % ordered.length]
      const score =
        calculateNodeDistance(current, candidate) +
        calculateNodeDistance(candidate, next) -
        calculateNodeDistance(current, next)

      if (score < bestScore) {
        bestScore = score
        bestInsertAt = index + 1
      }
    }

    ordered.splice(bestInsertAt, 0, candidate)
  }

  return ordered
}

function nodePointToGeoJsonPolygon(nodes: NodePoint[]) {
  if (nodes.length < 3) {
    return null
  }

  const orderedNodes = orderNodesByClosestPair(nodes)
  const ring = orderedNodes.map((node) => [node.lng, node.lat])
  const first = ring[0]
  const last = ring[ring.length - 1]

  if (first[0] !== last[0] || first[1] !== last[1]) {
    ring.push(first)
  }

  return {
    type: 'Polygon',
    coordinates: [ring],
  }
}

function isPointInsideProperty(point: NodePoint, polygon: NodePoint[]) {
  if (polygon.length < 3) {
    return false
  }

  const x = point.lng
  const y = point.lat
  let inside = false

  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const xi = polygon[i].lng
    const yi = polygon[i].lat
    const xj = polygon[j].lng
    const yj = polygon[j].lat

    const intersects = yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / ((yj - yi) || 1e-12) + xi
    if (intersects) {
      inside = !inside
    }
  }

  return inside
}


const defaultTheme: ThemeConfig = {
  colors: {
    background: '#08111f',
    backgroundAlt: '#0f1a2e',
    surface: '#111d33',
    surfaceAlt: '#162643',
    text: '#edf2ff',
    muted: '#9eb0cd',
    border: 'rgba(186, 205, 255, 0.14)',
    primary: '#f7b955',
    primarySoft: 'rgba(247, 185, 85, 0.14)',
    success: '#4dd4a3',
    warning: '#f3c969',
    danger: '#ff7a7a',
  },
  typography: {
    heading: '"Georgia", "Times New Roman", serif',
    body: '"Trebuchet MS", "Segoe UI", sans-serif',
    mono: '"SFMono-Regular", "Cascadia Mono", monospace',
  },
  fontSizes: {
    display: 'clamp(2.4rem, 5vw, 4.8rem)',
    title: '1.1rem',
    body: '0.98rem',
    small: '0.82rem',
  },
}

const markerDefault = L.icon({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
})

const draftNodeIcon = L.divIcon({
  className: 'draft-node-marker',
  iconSize: [12, 12],
  iconAnchor: [6, 6],
})

L.Marker.prototype.options.icon = markerDefault

function applyTheme(theme: ThemeConfig) {
  const root = document.documentElement

  root.style.setProperty('--color-background', theme.colors.background)
  root.style.setProperty('--color-background-alt', theme.colors.backgroundAlt)
  root.style.setProperty('--color-surface', theme.colors.surface)
  root.style.setProperty('--color-surface-alt', theme.colors.surfaceAlt)
  root.style.setProperty('--color-text', theme.colors.text)
  root.style.setProperty('--color-muted', theme.colors.muted)
  root.style.setProperty('--color-border', theme.colors.border)
  root.style.setProperty('--color-primary', theme.colors.primary)
  root.style.setProperty('--color-primary-soft', theme.colors.primarySoft)
  root.style.setProperty('--color-success', theme.colors.success)
  root.style.setProperty('--color-warning', theme.colors.warning)
  root.style.setProperty('--color-danger', theme.colors.danger)
  root.style.setProperty('--font-heading', theme.typography.heading)
  root.style.setProperty('--font-body', theme.typography.body)
  root.style.setProperty('--font-mono', theme.typography.mono)
  root.style.setProperty('--font-size-display', theme.fontSizes.display)
  root.style.setProperty('--font-size-title', theme.fontSizes.title)
  root.style.setProperty('--font-size-body', theme.fontSizes.body)
  root.style.setProperty('--font-size-small', theme.fontSizes.small)
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  if (!API_BASE_URL) {
    throw new Error('API_BASE_URL not configured')
  }

  const isFormData = typeof FormData !== 'undefined' && init?.body instanceof FormData
  const headers = new Headers(init?.headers ?? {})

  if (!isFormData && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers,
    ...init,
  })

  if (!response.ok) {
    let details = ''

    try {
      const payload = await response.json()
      details = String(payload?.error ?? payload?.message ?? '')
    } catch {
      details = ''
    }

    const suffix = details ? `: ${details}` : ''
    throw new Error(`Request failed with status ${response.status}${suffix}`)
  }

  return (await response.json()) as T
}

function App() {
  const [themeLoaded, setThemeLoaded] = useState(false)
  const [session, setSession] = useState<AccountSummary | null>(null)
  const [token, setToken] = useState('')
  const [properties, setProperties] = useState<Property[]>([])
  const [classifications, setClassifications] = useState<LotClassification[]>([])
  const [authStatus, setAuthStatus] = useState(
    'La autenticación se conecta a tu base privada del administrador.',
  )
  const [loginUsername, setLoginUsername] = useState('admin')
  const [loginPassword, setLoginPassword] = useState('')
  const [loginMessage, setLoginMessage] = useState('')
  const [selectedPropertyId, setSelectedPropertyId] = useState('')
  const [newPropertyName, setNewPropertyName] = useState('')
  const [newPropertyRegion, setNewPropertyRegion] = useState('')
  const [newPropertyResponsible, setNewPropertyResponsible] = useState('')
  const [newPropertyCropType, setNewPropertyCropType] = useState('Caña de Azúcar')
  const [newPropertyWateringFrequency, setNewPropertyWateringFrequency] = useState('4')
  const [newPropertyMessage, setNewPropertyMessage] = useState('')
  const [editingPropertyId, setEditingPropertyId] = useState('')
  const [editingPropertyName, setEditingPropertyName] = useState('')
  const [editingPropertyResponsible, setEditingPropertyResponsible] = useState('')
  const [editingPropertyCropType, setEditingPropertyCropType] = useState('')
  const [editingPropertyWateringFrequency, setEditingPropertyWateringFrequency] = useState('0')
  const [editingPropertyNotes, setEditingPropertyNotes] = useState('')
  const [propertyEditMessage, setPropertyEditMessage] = useState('')
  const [selectedNodeId, setSelectedNodeId] = useState('')
  const [editingNodeName, setEditingNodeName] = useState('')
  const [editingNodeResponsible, setEditingNodeResponsible] = useState('')
  const [editingNodeArea, setEditingNodeArea] = useState('')
  const [editingNodeNotes, setEditingNodeNotes] = useState('')
  const [actionPlanItems, setActionPlanItems] = useState<ActionPlanItem[]>([])
  const [newActionPlanEntry, setNewActionPlanEntry] = useState('')
  const [editingNodeClassificationId, setEditingNodeClassificationId] = useState('')
  const [editingNodeMessage, setEditingNodeMessage] = useState('')
  const [isDrawingLot, setIsDrawingLot] = useState(false)
  const [draftLotNodes, setDraftLotNodes] = useState<NodePoint[]>([])
  const [kmlFile, setKmlFile] = useState<File | null>(null)
  const [kmlRegion, setKmlRegion] = useState('')
  const [kmlResponsible, setKmlResponsible] = useState('')
  const [kmlImportMessage, setKmlImportMessage] = useState('')
  const [isImportingKml, setIsImportingKml] = useState(false)
  const [expandedPropertyId, setExpandedPropertyId] = useState('')

  const orderedProperties = useMemo(() => {
    return [...properties].sort((left, right) => {
      const leftIndex = PROPERTY_ORDER.findIndex((name) => name.toLowerCase() === left.name.toLowerCase())
      const rightIndex = PROPERTY_ORDER.findIndex((name) => name.toLowerCase() === right.name.toLowerCase())

      const normalizedLeft = leftIndex === -1 ? Number.MAX_SAFE_INTEGER : leftIndex
      const normalizedRight = rightIndex === -1 ? Number.MAX_SAFE_INTEGER : rightIndex

      if (normalizedLeft !== normalizedRight) {
        return normalizedLeft - normalizedRight
      }

      return left.name.localeCompare(right.name)
    })
  }, [properties])

  const visibleProperties = useMemo(() => {
    return orderedProperties.filter((property) => PROPERTY_ORDER_LOOKUP.has(property.name.toLowerCase()))
  }, [orderedProperties])

  const orderedVisibleProperties = useMemo(() => {
    return visibleProperties.map((property) => ({
      ...property,
      lots: sortLotsForProperty(property.name, property.lots),
    }))
  }, [visibleProperties])

  const mapProperties = useMemo(() => {
    return orderedProperties.map((property) => ({
      ...property,
      lots: sortLotsForProperty(property.name, property.lots),
    }))
  }, [orderedProperties])

  const activeProperty = mapProperties.find((p) => p.id === selectedPropertyId)
  const isAdmin = session?.role === 'admin'

  function getDisplaySubpredios(property: Property): DisplaySubpredio[] {
    const template = SUBPREDIOS_BY_PROPERTY[normalizeLabel(property.name)] ?? []

    if (template.length === 0) {
      return property.lots.map((lot) => ({
        id: lot.id,
        title: lot.name,
        subtitle: [lot.responsible].filter(Boolean).join(' · '),
        lotId: lot.id,
      }))
    }

    const lotBuckets = new Map<string, Lot[]>()

    for (const lot of property.lots) {
      const key = normalizeLabel(lot.name)
      const bucket = lotBuckets.get(key) ?? []
      bucket.push(lot)
      lotBuckets.set(key, bucket)
    }

    const usedIds = new Set<string>()
    const result: DisplaySubpredio[] = []

    template.forEach((name, index) => {
      const key = normalizeLabel(name)
      const bucket = lotBuckets.get(key) ?? []
      const lot = bucket.shift()

      if (lot) {
        usedIds.add(lot.id)
        result.push({
          id: lot.id,
          title: lot.name,
          subtitle: [lot.responsible].filter(Boolean).join(' · '),
          lotId: lot.id,
        })
        return
      }

      result.push({
        id: `template-${property.id}-${index}`,
        title: name,
        subtitle: 'Lote pendiente de registrar',
        lotId: null,
      })
    })

    const extraLots = property.lots.filter((lot) => !usedIds.has(lot.id))

    for (const lot of extraLots) {
      result.push({
        id: lot.id,
        title: lot.name,
        subtitle: [lot.responsible].filter(Boolean).join(' · '),
        lotId: lot.id,
      })
    }

    return result
  }

  function getDefaultNodeId(property: Property) {
    return getDisplaySubpredios(property)[0]?.id ?? ''
  }

  useEffect(() => {
    if (mapProperties.length === 0) {
      return
    }

    if (!selectedPropertyId || !mapProperties.some((property) => property.id === selectedPropertyId)) {
      const visibleProp = orderedVisibleProperties[0]
      if (visibleProp) {
        setSelectedPropertyId(visibleProp.id)
        setExpandedPropertyId(visibleProp.id)
        setSelectedNodeId(getDefaultNodeId(visibleProp))
      }
    }
  }, [selectedPropertyId, mapProperties, orderedVisibleProperties])

  function selectProperty(propertyId: string) {
    if (isDrawingLot && propertyId === selectedPropertyId) {
      return
    }

    const property = orderedVisibleProperties.find((item) => item.id === propertyId)

    setSelectedPropertyId(propertyId)
    setExpandedPropertyId(propertyId)
    setSelectedNodeId(property ? getDefaultNodeId(property) : '')
    setIsDrawingLot(false)
    setDraftLotNodes([])
  }

  function selectNode(propertyId: string, nodeId: string) {
    setSelectedPropertyId(propertyId)
    setExpandedPropertyId(propertyId)
    setSelectedNodeId(nodeId)
    setIsDrawingLot(false)
    setDraftLotNodes([])
  }

  useEffect(() => {
    fetch('/config/theme.json')
      .then((response) => response.json())
      .then((theme: ThemeConfig) => {
        applyTheme(theme)
        setThemeLoaded(true)
      })
      .catch(() => {
        applyTheme(defaultTheme)
        setThemeLoaded(true)
      })
  }, [])

  const authHeader = useMemo(() => {
    if (!token) {
      return undefined
    }

    return { Authorization: `Bearer ${token}` }
  }, [token])

  useEffect(() => {
    if (!activeProperty) {
      return
    }

    setExpandedPropertyId(activeProperty.id)

    setEditingPropertyId(activeProperty.id)
    setEditingPropertyName(activeProperty.name)
    setEditingPropertyResponsible(activeProperty.responsible)
    setEditingPropertyCropType(activeProperty.cropType)
    setEditingPropertyWateringFrequency(String(activeProperty.wateringFrequencyPerMonth ?? 0))
    setEditingPropertyNotes(activeProperty.notes)

    if (!selectedNodeId) {
      setSelectedNodeId(getDefaultNodeId(activeProperty))
    }
  }, [activeProperty, selectedNodeId])

  useEffect(() => {
    if (!activeProperty) {
      return
    }

    const selectedNode = activeProperty.lots.find((lot) => lot.id === selectedNodeId)
    const selectedSubpredio = getDisplaySubpredios(activeProperty).find(
      (subpredio) => subpredio.id === selectedNodeId,
    )

    if (selectedNode) {
      setEditingNodeName(selectedNode.name)
      setEditingNodeResponsible(selectedNode.responsible)
      setEditingNodeArea(selectedNode.areaHectares?.toString() ?? '')
      setEditingNodeNotes(selectedNode.notes)
      setActionPlanItems(parseActionPlanItems(selectedNode.actionPlan))
      setNewActionPlanEntry('')
      setEditingNodeClassificationId(String(selectedNode.classificationId))
      return
    }

    if (selectedSubpredio) {
      setEditingNodeName(selectedSubpredio.title)
      setEditingNodeResponsible('')
      setEditingNodeArea('')
      setEditingNodeNotes('')
      setActionPlanItems([])
      setNewActionPlanEntry('')
      if (!editingNodeClassificationId && classifications[0]) {
        setEditingNodeClassificationId(String(classifications[0].id))
      }
      return
    }

    if (!selectedNodeId) {
      setSelectedNodeId(getDefaultNodeId(activeProperty))
    }
  }, [activeProperty, selectedNodeId, classifications, editingNodeClassificationId])

  useEffect(() => {
    if (!editingPropertyId) {
      return
    }

    const timeoutId = setTimeout(() => {
      autoSaveProperty(editingPropertyId, {
        responsible: editingPropertyResponsible.trim(),
        cropType: editingPropertyCropType.trim(),
        wateringFrequencyPerMonth: Number(editingPropertyWateringFrequency || 0),
        notes: editingPropertyNotes.trim(),
      })
    }, 1000)

    return () => clearTimeout(timeoutId)
  }, [editingPropertyResponsible, editingPropertyCropType, editingPropertyWateringFrequency, editingPropertyNotes, editingPropertyId])

  useEffect(() => {
    if (!selectedNodeId || !activeProperty?.lots.some((lot) => lot.id === selectedNodeId)) {
      return
    }

    const selectedLot = activeProperty.lots.find((lot) => lot.id === selectedNodeId)
    const resolvedClassificationId = Number(
      editingNodeClassificationId || selectedLot?.classificationId || classifications[0]?.id || 0,
    )

    const timeoutId = setTimeout(() => {
      autoSaveNode(selectedNodeId, {
        name: editingNodeName.trim(),
        classificationId: resolvedClassificationId,
        responsible: editingNodeResponsible.trim(),
        areaHectares: editingNodeArea ? Number(editingNodeArea) : null,
        notes: editingNodeNotes.trim(),
        actionPlan: serializeActionPlanItems(actionPlanItems),
      })
    }, 1000)

    return () => clearTimeout(timeoutId)
  }, [
    activeProperty,
    actionPlanItems,
    classifications,
    editingNodeArea,
    editingNodeClassificationId,
    editingNodeName,
    editingNodeNotes,
    editingNodeResponsible,
    selectedNodeId,
  ])

  async function loadProperties() {
    if (!session || !token) {
      return
    }

    const result = await requestJson<{ properties: Property[] }>('/properties', {
      headers: authHeader,
    })

    setProperties(result.properties)

    const firstVisibleProperty = result.properties.find((property) =>
      PROPERTY_ORDER_LOOKUP.has(property.name.toLowerCase()),
    )

    if (firstVisibleProperty && !selectedPropertyId) {
      setSelectedPropertyId(firstVisibleProperty.id)
      setExpandedPropertyId(firstVisibleProperty.id)
      setSelectedNodeId(getDefaultNodeId(firstVisibleProperty))
    }
  }

  useEffect(() => {
    if (!session || !token) {
      return
    }

    loadProperties().catch(() => console.error('Failed to load properties'))
  }, [session, token, authHeader])

  useEffect(() => {
    if (!session || !token) {
      return
    }

    requestJson<{ classifications: LotClassification[] }>('/lots/classifications', {
      headers: authHeader,
    })
      .then((result) => setClassifications(result.classifications))
      .catch(() => console.error('Failed to load classifications'))
  }, [session, token, authHeader])

  function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setLoginMessage('')

    if (!API_BASE_URL) {
      setAuthStatus(
        'Define VITE_API_BASE_URL para autenticar contra la base privada del administrador.',
      )
      return
    }

    requestJson<{ session: AccountSummary; token: string }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({
        username: loginUsername,
        password: loginPassword,
      }),
    })
      .then((result) => {
        setSession(result.session)
        setToken(result.token)
        setAuthStatus('Sesión iniciada correctamente.')
      })
      .catch(() => {
        setLoginMessage(
          'No fue posible iniciar sesión. Revisa la conexión con la base privada del administrador.',
        )
      })
  }

  function handleLogout() {
    setSession(null)
    setToken('')
    setProperties([])
    setClassifications([])
    setSelectedPropertyId('')
    setExpandedPropertyId('')
    setSelectedNodeId('')
  }

  async function handleCreateProperty(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setNewPropertyMessage('')

    if (!session || session.role !== 'admin' || !authHeader) {
      return
    }

    if (!newPropertyName.trim()) {
      setNewPropertyMessage('El nombre del predio es requerido.')
      return
    }

    try {
      const result = await requestJson<{ property: Property }>('/properties', {
        method: 'POST',
        headers: authHeader,
        body: JSON.stringify({
          name: newPropertyName.trim(),
          responsible: newPropertyResponsible.trim() || 'Sin asignar',
          region: newPropertyRegion.trim() || 'Veracruz',
          cropType: newPropertyCropType.trim() || 'Caña de Azúcar',
          isSugarcane: true,
          wateringFrequencyPerMonth: Number(newPropertyWateringFrequency || 0),
        }),
      })

      setProperties((current) => [...current, result.property])
      setSelectedPropertyId(result.property.id)
      setExpandedPropertyId(result.property.id)
          setSelectedNodeId(getDefaultNodeId(result.property))
      setNewPropertyName('')
      setNewPropertyRegion('')
      setNewPropertyResponsible('')
      setNewPropertyCropType('Caña de Azúcar')
      setNewPropertyWateringFrequency('4')
      setNewPropertyMessage('Predio creado exitosamente.')
    } catch {
      setNewPropertyMessage('No fue posible crear el predio.')
    }
  }

  async function handleDeleteProperty(propertyId: string) {
    if (!session || session.role !== 'admin' || !authHeader) {
      return
    }

    if (!confirm('¿Eliminar este predio?')) {
      return
    }

    try {
      await requestJson('/properties/' + propertyId, {
        method: 'DELETE',
        headers: authHeader,
      })

      setProperties((current) => current.filter((p) => p.id !== propertyId))
      if (selectedPropertyId === propertyId) {
        const nextPropertyId = properties.find((item) => item.id !== propertyId)?.id ?? ''
        setSelectedPropertyId(nextPropertyId)
        setExpandedPropertyId(nextPropertyId)
        setSelectedNodeId('')
      }
    } catch {
      alert('No fue posible eliminar el predio.')
    }
  }

  async function autoSaveProperty(propertyId: string, data: any) {
    if (!session || session.role !== 'admin' || !authHeader || !propertyId) {
      return
    }

    try {
      await requestJson<{ ok: boolean }>(`/properties/${propertyId}`, {
        method: 'PUT',
        headers: authHeader,
        body: JSON.stringify(data),
      })

      setProperties((current) =>
        current.map((property) =>
          property.id === propertyId
            ? {
                ...property,
                ...data,
              }
            : property,
        ),
      )
    } catch {
      // Silent error for autosave
    }
  }

  async function autoSaveNode(lotId: string, data: any) {
    if (!session || session.role !== 'admin' || !authHeader || !lotId) {
      return
    }

    try {
      await requestJson<{ ok: boolean }>(`/lots/${lotId}`, {
        method: 'PUT',
        headers: authHeader,
        body: JSON.stringify(data),
      })

      setProperties((current) =>
        current.map((property) => ({
          ...property,
          lots: property.lots.map((lot) =>
            lot.id === lotId
              ? {
                  ...lot,
                  ...data,
                }
              : lot,
          ),
        })),
      )
    } catch {
      // Silent error for autosave
    }
  }

  async function handleSaveProperty(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setPropertyEditMessage('')

    if (!session || session.role !== 'admin' || !authHeader || !editingPropertyId) {
      return
    }

    try {
      const result = await requestJson<{ ok: boolean }>(`/properties/${editingPropertyId}`, {
        method: 'PUT',
        headers: authHeader,
        body: JSON.stringify({
          name: editingPropertyName.trim(),
          responsible: editingPropertyResponsible.trim(),
          cropType: editingPropertyCropType.trim(),
          wateringFrequencyPerMonth: Number(editingPropertyWateringFrequency || 0),
          notes: editingPropertyNotes.trim(),
        }),
      })

      if (result.ok) {
        setProperties((current) =>
          current.map((property) =>
            property.id === editingPropertyId
              ? {
                  ...property,
                  name: editingPropertyName.trim(),
                  responsible: editingPropertyResponsible.trim(),
                  cropType: editingPropertyCropType.trim(),
                  wateringFrequencyPerMonth: Number(editingPropertyWateringFrequency || 0),
                  notes: editingPropertyNotes.trim(),
                }
              : property,
          ),
        )
        setPropertyEditMessage('Predio actualizado correctamente.')
      }
    } catch {
      setPropertyEditMessage('No fue posible actualizar el predio.')
    }
  }

  function clearNodeForm() {
    setSelectedNodeId('')
    setEditingNodeName('')
    setEditingNodeResponsible('')
    setEditingNodeArea('')
    setEditingNodeNotes('')
    setActionPlanItems([])
    setNewActionPlanEntry('')
    setEditingNodeClassificationId('')
    setEditingNodeMessage('')
    setIsDrawingLot(false)
    setDraftLotNodes([])
  }

  function addActionPlanItem() {
    const value = newActionPlanEntry.trim()
    if (!value) {
      return
    }

    setActionPlanItems((current) => [
      ...current,
      {
        id: `task-${Date.now()}`,
        text: value,
        done: false,
      },
    ])
    setNewActionPlanEntry('')
  }

  function removeActionPlanItem(itemId: string) {
    setActionPlanItems((current) => current.filter((item) => item.id !== itemId))
  }

  function toggleActionPlanItem(itemId: string) {
    setActionPlanItems((current) =>
      current.map((item) =>
        item.id === itemId
          ? {
              ...item,
              done: !item.done,
            }
          : item,
      ),
    )
  }

  function startLotDrawing() {
    setSelectedNodeId('')
    setEditingNodeName('')
    setEditingNodeArea('')
    setEditingNodeNotes('')
    setActionPlanItems([])
    setNewActionPlanEntry('')
    setEditingNodeResponsible('')
    setIsDrawingLot(true)
    setDraftLotNodes([])
    setEditingNodeMessage('Haz clic dentro del predio para colocar nodos del nuevo lote.')
  }

  function undoDraftLotNode() {
    setDraftLotNodes((current) => current.slice(0, -1))
  }

  function clearDraftLotNodes() {
    setDraftLotNodes([])
  }

  function removeDraftLotNode(nodeIndex: number) {
    setDraftLotNodes((current) => current.filter((_, index) => index !== nodeIndex))
  }

  function updateDraftLotNode(nodeIndex: number, point: NodePoint) {
    setDraftLotNodes((current) =>
      current.map((node, index) => (index === nodeIndex ? point : node)),
    )
  }

  function handleDraftNodeFromMap(point: NodePoint) {
    if (!isDrawingLot || !activeProperty) {
      return
    }

    if (!isPointInsideProperty(point, activeProperty.nodes)) {
      setEditingNodeMessage('El nodo debe colocarse dentro del predio seleccionado.')
      return
    }

    setDraftLotNodes((current) => [...current, point])
    setEditingNodeMessage('Nodo agregado al lote en construcción.')
  }

  async function handleDeleteLot(lotId: string) {
    if (!session || session.role !== 'admin' || !authHeader || !selectedPropertyId) {
      return
    }

    if (!confirm('¿Eliminar este lote?')) {
      return
    }

    try {
      await requestJson(`/lots/${lotId}`, {
        method: 'DELETE',
        headers: authHeader,
      })

      setProperties((current) =>
        current.map((property) =>
          property.id === selectedPropertyId
            ? {
                ...property,
                lots: property.lots.filter((lot) => lot.id !== lotId),
              }
            : property,
        ),
      )

      if (selectedNodeId === lotId) {
        setSelectedNodeId('')
      }

      setEditingNodeMessage('Lote eliminado correctamente.')
    } catch {
      setEditingNodeMessage('No fue posible eliminar el lote.')
    }
  }

  async function handleSaveNode(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setEditingNodeMessage('')

    if (!session || session.role !== 'admin' || !authHeader) {
      setEditingNodeMessage('Solo el administrador puede guardar lotes.')
      return
    }

    if (!selectedPropertyId || !activeProperty) {
      setEditingNodeMessage('Selecciona un predio valido antes de guardar el lote.')
      return
    }

    if (!editingNodeName.trim()) {
      setEditingNodeMessage('Nombre del lote es requerido.')
      return
    }

    const selectedLot = activeProperty?.lots.find((lot) => lot.id === selectedNodeId)
    const resolvedClassificationId = Number(
      editingNodeClassificationId || selectedLot?.classificationId || classifications[0]?.id || 0,
    )

    if (!resolvedClassificationId) {
      setEditingNodeMessage('No hay tipo interno disponible para guardar el lote.')
      return
    }

    const payload = {
      name: editingNodeName.trim(),
      classificationId: resolvedClassificationId,
      responsible: editingNodeResponsible.trim(),
      areaHectares: editingNodeArea ? Number(editingNodeArea) : null,
      notes: editingNodeNotes.trim(),
      actionPlan: serializeActionPlanItems(actionPlanItems),
    }

    try {
      if (selectedLot) {
        await requestJson(`/lots/${selectedNodeId}`, {
          method: 'PUT',
          headers: authHeader,
          body: JSON.stringify(payload),
        })

        setProperties((current) =>
          current.map((property) =>
            property.id === selectedPropertyId
              ? {
                  ...property,
                  lots: property.lots.map((lot) =>
                    lot.id === selectedNodeId
                      ? {
                          ...lot,
                          ...payload,
                          classificationCode:
                            classifications.find((c) => c.id === payload.classificationId)?.code ??
                            lot.classificationCode,
                          classificationName:
                            classifications.find((c) => c.id === payload.classificationId)?.name ??
                            lot.classificationName,
                          colorHex:
                            classifications.find((c) => c.id === payload.classificationId)?.colorHex ??
                            lot.colorHex,
                        }
                      : lot,
                  ),
                }
              : property,
          ),
        )

        setEditingNodeMessage('Lote actualizado correctamente.')
      } else {
        const coordinatesGeojson = nodePointToGeoJsonPolygon(draftLotNodes)

        if (!coordinatesGeojson) {
          setEditingNodeMessage('Debes dibujar al menos 3 nodos dentro del predio para crear el lote.')
          return
        }

        const result = await requestJson<{ lot: Lot }>('/lots', {
          method: 'POST',
          headers: authHeader,
          body: JSON.stringify({
            propertyId: selectedPropertyId,
            coordinatesGeojson,
            ...payload,
          }),
        })

        setProperties((current) =>
          current.map((property) =>
            property.id === selectedPropertyId
              ? { ...property, lots: [...property.lots, result.lot] }
              : property,
          ),
        )

        setSelectedNodeId(result.lot.id)
        setIsDrawingLot(false)
        setDraftLotNodes([])
        setEditingNodeMessage('Lote creado correctamente.')
      }
    } catch (error) {
      const fallback = 'No fue posible guardar el lote.'
      setEditingNodeMessage(error instanceof Error ? error.message : fallback)
    }
  }

  async function handleImportKml(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setKmlImportMessage('')

    if (!session || session.role !== 'admin' || !authHeader) {
      return
    }

    if (!kmlFile) {
      setKmlImportMessage('Selecciona un archivo KML para importar.')
      return
    }

    const formData = new FormData()
    formData.append('kmlFile', kmlFile)

    if (kmlRegion.trim()) {
      formData.append('region', kmlRegion.trim())
    }

    if (kmlResponsible.trim()) {
      formData.append('responsible', kmlResponsible.trim())
    }

    setIsImportingKml(true)

    try {
      const result = await requestJson<{
        importedCount: number
        skipped: number
      }>('/properties/import/kml', {
        method: 'POST',
        headers: authHeader,
        body: formData,
      })

      await loadProperties()

      setKmlFile(null)
      setKmlRegion('')
      setKmlResponsible('')
      setKmlImportMessage(
        `Importación completada: ${result.importedCount} predios cargados, ${result.skipped} omitidos.`,
      )
    } catch {
      setKmlImportMessage('No fue posible importar el archivo KML.')
    } finally {
      setIsImportingKml(false)
    }
  }

  if (!themeLoaded) {
    return (
      <main className="loading-shell">
        <p>Preparando la configuración visual...</p>
      </main>
    )
  }

  if (!session) {
    return (
      <main className="auth-page">
        <section className="hero-panel surface-card">
          <div className="hero-panel__label">Chequeo Predios</div>
          <h1>Plataforma GIS agrícola privada</h1>
          <p>
            Sistema de administración de predios y lotes con clasificación real de
            campo. Solo el administrador edita; otros consultan.
          </p>
          <div className="hero-panel__stats">
            <article>
              <strong>Privada</strong>
              <span>acceso controlado</span>
            </article>
            <article>
              <strong>Lotes</strong>
              <span>clasificados por tipo</span>
            </article>
            <article>
              <strong>OSM</strong>
              <span>mapa satelital</span>
            </article>
          </div>
        </section>

        <section className="surface-card auth-card">
          <div className="section-heading">
            <span>Acceso seguro</span>
            <h2>Inicia sesión</h2>
          </div>
          <form className="auth-form" onSubmit={handleLogin}>
            <p className="form-message">{authStatus}</p>
            <label>
              <span>Usuario</span>
              <input
                type="text"
                value={loginUsername}
                onChange={(event) => setLoginUsername(event.target.value)}
                placeholder="admin"
                autoComplete="username"
              />
            </label>
            <label>
              <span>Contraseña</span>
              <input
                type="password"
                value={loginPassword}
                onChange={(event) => setLoginPassword(event.target.value)}
                placeholder="Ingresa tu contraseña"
                autoComplete="current-password"
              />
            </label>

            {loginMessage ? <p className="form-message">{loginMessage}</p> : null}

            <button type="submit" className="primary-button">
              Entrar al sistema
            </button>
          </form>
        </section>
      </main>
    )
  }

  return (
    <main className="dashboard-shell gis-layout">
      <aside className="sidebar surface-card gis-sidebar">
        <div className="brand-block">
          <div>
            <p className="brand-block__eyebrow">Chequeo Predios</p>
            <h1>GIS Agrícola</h1>
          </div>
          <button className="ghost-button" type="button" onClick={handleLogout}>
            Salir
          </button>
        </div>

        <div className="session-card">
          <span>Sesión activa</span>
          <strong>{session.name}</strong>
          <p>@{session.username} · {session.role}</p>
        </div>

        <section className="surface-card sidebar-section">
          <div className="section-heading">
            <span>Predios</span>
            <h2>Selecciona un predio</h2>
          </div>

          <div className="property-list">
            {orderedVisibleProperties.map((prop) => (
              <div key={prop.id} className={`property-item ${selectedPropertyId === prop.id ? 'active' : ''}`}>
                <div className="property-item__header">
                  <button
                    type="button"
                    className="property-item__button"
                    onClick={() => selectProperty(prop.id)}
                  >
                    <strong>{prop.name}</strong>
                    <span>{prop.region}</span>
                  </button>
                  {isAdmin && (
                    <button
                      type="button"
                      className="danger-button-small"
                      onClick={(e) => {
                        e.stopPropagation()
                        handleDeleteProperty(prop.id)
                      }}
                    >
                      ✕
                    </button>
                  )}
                </div>
                {expandedPropertyId === prop.id && (
                  <div className="property-node-list">
                    <p className="property-node-empty">
                      {getDisplaySubpredios(prop).length} lote{getDisplaySubpredios(prop).length !== 1 ? 's' : ''}
                    </p>
                    {getDisplaySubpredios(prop).map((node) => (
                      <button
                        key={node.id}
                        type="button"
                        className={`property-node-item ${selectedNodeId === node.id ? 'active' : ''}`}
                        onClick={() => selectNode(prop.id, node.id)}
                      >
                        <span className="property-node-item__title">{node.title}</span>
                        <span className="property-node-item__meta">{node.subtitle}</span>
                      </button>
                    ))}
                    {getDisplaySubpredios(prop).length === 0 && (
                      <p className="property-node-empty">Este predio todavía no tiene lotes.</p>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>

          {isAdmin && (
            <>
              {activeProperty && (
                <form className="new-property-form" onSubmit={handleSaveProperty}>
                  <div className="section-heading">
                    <span>Editar predio</span>
                    <h3>{activeProperty.name}</h3>
                  </div>
                  <input
                    type="text"
                    value={editingPropertyResponsible}
                    onChange={(event) => setEditingPropertyResponsible(event.target.value)}
                    placeholder="Responsable"
                  />
                  <input
                    type="text"
                    value={editingPropertyCropType}
                    onChange={(event) => setEditingPropertyCropType(event.target.value)}
                    placeholder="Cultivo"
                  />
                  <input
                    type="number"
                    min="0"
                    value={editingPropertyWateringFrequency}
                    onChange={(event) => setEditingPropertyWateringFrequency(event.target.value)}
                    placeholder="Riegos por mes"
                  />
                  <textarea
                    value={editingPropertyNotes}
                    onChange={(event) => setEditingPropertyNotes(event.target.value)}
                    placeholder="Descripción del predio"
                    rows={3}
                    style={{ resize: 'vertical', padding: '8px', fontSize: 'inherit' }}
                  />
                  <button type="submit" className="primary-button">
                    Guardar predio
                  </button>
                  {propertyEditMessage && (
                    <p className="form-message">{propertyEditMessage}</p>
                  )}
                </form>
              )}

              <form className="new-property-form" onSubmit={handleCreateProperty}>
                <input
                  type="text"
                  value={newPropertyName}
                  onChange={(event) => setNewPropertyName(event.target.value)}
                  placeholder="Nombre del predio"
                  required
                />
                <input
                  type="text"
                  value={newPropertyResponsible}
                  onChange={(event) => setNewPropertyResponsible(event.target.value)}
                  placeholder="Responsable (ej: Juan García)"
                />
                <input
                  type="text"
                  value={newPropertyRegion}
                  onChange={(event) => setNewPropertyRegion(event.target.value)}
                  placeholder="Región (ej: Veracruz - Zona Centro)"
                />
                <input
                  type="text"
                  value={newPropertyCropType}
                  onChange={(event) => setNewPropertyCropType(event.target.value)}
                  placeholder="Cultivo (ej: Caña de Azúcar)"
                />
                <input
                  type="number"
                  min="0"
                  value={newPropertyWateringFrequency}
                  onChange={(event) => setNewPropertyWateringFrequency(event.target.value)}
                  placeholder="Riegos por mes"
                />
                <button type="submit" className="primary-button">
                  Agregar predio
                </button>
                {newPropertyMessage && (
                  <p className="form-message">{newPropertyMessage}</p>
                )}
              </form>

              <form className="new-property-form" onSubmit={handleImportKml}>
                <label>
                  <span>Importar predios desde KML</span>
                  <input
                    type="file"
                    accept=".kml,application/vnd.google-earth.kml+xml"
                    onChange={(event) =>
                      setKmlFile(event.target.files?.[0] ?? null)
                    }
                  />
                </label>
                <input
                  type="text"
                  value={kmlResponsible}
                  onChange={(event) => setKmlResponsible(event.target.value)}
                  placeholder="Responsable por defecto (opcional)"
                />
                <input
                  type="text"
                  value={kmlRegion}
                  onChange={(event) => setKmlRegion(event.target.value)}
                  placeholder="Región por defecto (opcional)"
                />
                <button type="submit" className="secondary-button" disabled={isImportingKml}>
                  {isImportingKml ? 'Importando KML...' : 'Importar KML'}
                </button>
                {kmlImportMessage && <p className="form-message">{kmlImportMessage}</p>}
              </form>
            </>
          )}
        </section>
      </aside>

      <section className="main-panel gis-main">
        {properties.length > 0 ? (
          <>
            <header className="surface-card page-header">
              <div>
                <span className="page-header__eyebrow">
                  {activeProperty ? `Predio: ${activeProperty.name}` : 'Predios cargados'}
                </span>
                <h2>{activeProperty?.region ?? 'Vista general de predios'}</h2>
              </div>
              <p>
                {activeProperty
                  ? `${activeProperty.lots.length} lote${activeProperty.lots.length !== 1 ? 's' : ''}`
                  : `${properties.length} predios`}
              </p>
            </header>

            <div className="gis-content">
              <section className="surface-card map-card">
                <PropertyMap
                  properties={mapProperties}
                  selectedPropertyId={selectedPropertyId}
                  selectedNodeId={selectedNodeId}
                  onSelectProperty={selectProperty}
                  onSelectNode={selectNode}
                  isAdmin={isAdmin}
                  editingPropertyId={editingPropertyId}
                  editingPropertyResponsible={editingPropertyResponsible}
                  editingPropertyCropType={editingPropertyCropType}
                  editingPropertyWateringFrequency={editingPropertyWateringFrequency}
                  editingPropertyNotes={editingPropertyNotes}
                  onPropertyChange={(field, value) => {
                    if (field === 'responsible') setEditingPropertyResponsible(value)
                    else if (field === 'cropType') setEditingPropertyCropType(value)
                    else if (field === 'wateringFrequency') setEditingPropertyWateringFrequency(value)
                    else if (field === 'notes') setEditingPropertyNotes(value)
                  }}
                  editingNodeResponsible={editingNodeResponsible}
                  editingNodeArea={editingNodeArea}
                  editingNodeNotes={editingNodeNotes}
                  onNodeChange={(field, value) => {
                    if (field === 'responsible') setEditingNodeResponsible(value)
                    else if (field === 'area') setEditingNodeArea(value)
                    else if (field === 'notes') setEditingNodeNotes(value)
                  }}
                  isDrawingLot={isDrawingLot}
                  draftLotNodes={draftLotNodes}
                  onMapDraftNode={handleDraftNodeFromMap}
                  onRemoveDraftNode={removeDraftLotNode}
                  onUpdateDraftNode={updateDraftLotNode}
                />
              </section>

              <aside className="surface-card lots-sidebar">
                <div className="section-heading">
                  <span>Lote seleccionado</span>
                  <h3>Detalle</h3>
                </div>

                {activeProperty ? (
                  <div className="session-card">
                    <span>{activeProperty.name}</span>
                    {activeProperty.lots.find((lot) => lot.id === selectedNodeId) ? (
                      <>
                        <strong>
                          {activeProperty.lots.find((lot) => lot.id === selectedNodeId)?.name}
                        </strong>
                        <p>
                          Identificacion del lote
                        </p>
                        <p>
                          {activeProperty.lots.find((lot) => lot.id === selectedNodeId)?.notes ||
                            'Sin descripción registrada.'}
                        </p>
                      </>
                    ) : getDisplaySubpredios(activeProperty).find((node) => node.id === selectedNodeId) ? (
                      <>
                        <strong>
                          {getDisplaySubpredios(activeProperty).find((node) => node.id === selectedNodeId)?.title}
                        </strong>
                        <p>Lote pendiente de registrar.</p>
                      </>
                    ) : (
                      <p>Selecciona un lote para ver su información.</p>
                    )}
                  </div>
                ) : (
                  <div className="session-card">
                    <p>Selecciona un predio para ver sus lotes.</p>
                  </div>
                )}

                {isAdmin && (
                  <form className="new-lot-form" onSubmit={handleSaveNode}>
                    <div className="editor-actions" style={{ display: 'grid', gap: '8px' }}>
                      <button type="button" className="secondary-button" onClick={clearNodeForm}>
                        Nuevo lote
                      </button>
                      {!selectedNodeId && !isDrawingLot && (
                        <button
                          type="button"
                          className="secondary-button"
                          onClick={startLotDrawing}
                        >
                          Crear lote
                        </button>
                      )}
                      {isDrawingLot && !selectedNodeId && (
                        <>
                          <button type="button" className="ghost-button" onClick={undoDraftLotNode}>
                            Deshacer nodo
                          </button>
                          <button type="button" className="ghost-button" onClick={clearDraftLotNodes}>
                            Limpiar nodos
                          </button>
                          <p className="property-node-empty">
                            Nodos capturados: {draftLotNodes.length} (mínimo 3). Clic en el mapa para agregar, clic en nodo verde para eliminar.
                          </p>
                        </>
                      )}
                      {(selectedNodeId || isDrawingLot) && (
                        <button type="submit" className="primary-button">
                          Guardar lote
                        </button>
                      )}
                      {selectedNodeId && activeProperty?.lots.some((lot) => lot.id === selectedNodeId) && (
                        <button
                          type="button"
                          className="danger-button"
                          onClick={() => handleDeleteLot(selectedNodeId)}
                        >
                          Eliminar lote
                        </button>
                      )}
                    </div>
                    <input
                      type="text"
                      value={editingNodeName}
                      onChange={(event) => setEditingNodeName(event.target.value)}
                      placeholder="Nombre / identificación del lote"
                      required
                    />
                    <input
                      type="number"
                      step="0.1"
                      value={editingNodeArea}
                      onChange={(event) => setEditingNodeArea(event.target.value)}
                      placeholder="Área en hectáreas (opcional)"
                    />
                    <input
                      type="text"
                      value={editingNodeResponsible}
                      onChange={(event) => setEditingNodeResponsible(event.target.value)}
                      placeholder="Encargado del lote"
                    />
                    <textarea
                      value={editingNodeNotes}
                      onChange={(event) => setEditingNodeNotes(event.target.value)}
                      placeholder="Descripción del lote"
                      rows={2}
                      style={{ resize: 'vertical', padding: '8px', fontSize: 'inherit' }}
                    />

                    <div className="section-heading" style={{ marginTop: '8px' }}>
                      <span>Plan de acción mensual</span>
                      <h3>Actividades</h3>
                    </div>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <input
                        type="text"
                        value={newActionPlanEntry}
                        onChange={(event) => setNewActionPlanEntry(event.target.value)}
                        placeholder="Agregar actividad mensual"
                      />
                      <button type="button" className="secondary-button" onClick={addActionPlanItem}>
                        +
                      </button>
                    </div>
                    <div style={{ display: 'grid', gap: '6px' }}>
                      {actionPlanItems.map((item) => (
                        <div key={item.id} style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                          <input
                            type="checkbox"
                            checked={item.done}
                            onChange={() => toggleActionPlanItem(item.id)}
                            style={{ width: '18px', height: '18px' }}
                          />
                          <span style={{ flex: 1, textDecoration: item.done ? 'line-through' : 'none' }}>
                            {item.text}
                          </span>
                          <button
                            type="button"
                            className="danger-button-small"
                            onClick={() => removeActionPlanItem(item.id)}
                          >
                            ✕
                          </button>
                        </div>
                      ))}
                      {actionPlanItems.length === 0 && (
                        <p className="property-node-empty">Sin actividades mensuales aún.</p>
                      )}
                    </div>
                    {editingNodeMessage && <p className="form-message">{editingNodeMessage}</p>}
                  </form>
                )}
              </aside>
            </div>
          </>
        ) : (
          <div className="map-placeholder">
            <p>Selecciona un predio para ver su información y lotes.</p>
          </div>
        )}
      </section>
    </main>
  )
}

function PropertyBoundsController({ property }: { property: Property | undefined }) {
  const map = useMap()

  useEffect(() => {
    if (!property || property.nodes.length < 3) {
      return
    }

    const bounds = L.latLngBounds(property.nodes.map((node) => [node.lat, node.lng]))
    map.fitBounds(bounds.pad(0.15), { animate: true })
  }, [map, property])

  return null
}

function LotDrawingEvents({
  enabled,
  onMapDraftNode,
}: {
  enabled: boolean
  onMapDraftNode: (point: NodePoint) => void
}) {
  useMapEvents({
    click: (event) => {
      if (!enabled) {
        return
      }

      onMapDraftNode({
        lat: event.latlng.lat,
        lng: event.latlng.lng,
      })
    },
  })

  return null
}

function PropertyMap({
  properties,
  selectedPropertyId,
  selectedNodeId,
  onSelectProperty,
  onSelectNode,
  isAdmin,
  editingPropertyId,
  editingPropertyResponsible,
  editingPropertyCropType,
  editingPropertyWateringFrequency,
  editingPropertyNotes,
  onPropertyChange,
  editingNodeResponsible,
  editingNodeArea,
  editingNodeNotes,
  onNodeChange,
  isDrawingLot,
  draftLotNodes,
  onMapDraftNode,
  onRemoveDraftNode,
  onUpdateDraftNode,
}: {
  properties: Property[]
  selectedPropertyId: string
  selectedNodeId: string
  onSelectProperty: (propertyId: string) => void
  onSelectNode: (propertyId: string, nodeId: string) => void
  isAdmin: boolean
  editingPropertyId: string
  editingPropertyResponsible: string
  editingPropertyCropType: string
  editingPropertyWateringFrequency: string
  editingPropertyNotes: string
  onPropertyChange: (field: string, value: string) => void
  editingNodeResponsible: string
  editingNodeArea: string
  editingNodeNotes: string
  onNodeChange: (field: string, value: string) => void
  isDrawingLot: boolean
  draftLotNodes: NodePoint[]
  onMapDraftNode: (point: NodePoint) => void
  onRemoveDraftNode: (nodeIndex: number) => void
  onUpdateDraftNode: (nodeIndex: number, point: NodePoint) => void
}) {
  const [hoveredPropertyId, setHoveredPropertyId] = useState<string | null>(null)
  const propertyPopupRefs = useRef<Record<string, any>>({})
  const nodePopupRefs = useRef<Record<string, any>>({})
  const selectedProperty = properties.find((property) => property.id === selectedPropertyId)

  function getPolygonLayers(source: NodePoint[] | Lot['coordinatesGeojson']): [number, number][][] {
    if (Array.isArray(source)) {
      if (source.length < 3) {
        return []
      }

      return [source.map((point) => [point.lat, point.lng] as [number, number])]
    }

    if (!source?.coordinates) {
      return []
    }

    if (source.type === 'Polygon') {
      const ring = source.coordinates[0] ?? []
      return [
        ring.map((coord: number[]) => [coord[1], coord[0]] as [number, number]),
      ]
    }

    if (source.type === 'MultiPolygon') {
      return (source.coordinates as number[][][][])
        .map((polygon) => polygon?.[0] ?? [])
        .map((ring) =>
          ring.map((coord: number[]) => [coord[1], coord[0]] as [number, number]),
        )
        .filter((ring) => ring.length >= 3)
    }

    return []
  }

  useEffect(() => {
    if (isDrawingLot) {
      propertyPopupRefs.current[selectedPropertyId]?.closePopup?.()
      nodePopupRefs.current[selectedNodeId]?.closePopup?.()
      return
    }

    if (selectedPropertyId && propertyPopupRefs.current[selectedPropertyId]) {
      setTimeout(() => {
        propertyPopupRefs.current[selectedPropertyId]?.openPopup()
      }, 100)
    } else if (selectedNodeId && nodePopupRefs.current[selectedNodeId]) {
      setTimeout(() => {
        nodePopupRefs.current[selectedNodeId]?.openPopup()
      }, 100)
    }
  }, [isDrawingLot, selectedPropertyId, selectedNodeId])

  return (
    <MapContainer
      center={MAP_CENTER}
      zoom={11}
      className="leaflet-map"
      dragging
      scrollWheelZoom
      doubleClickZoom
      touchZoom
      keyboard
      boxZoom
    >
      <PropertyBoundsController property={selectedProperty} />
      <LotDrawingEvents enabled={isDrawingLot} onMapDraftNode={onMapDraftNode} />
      <TileLayer
        url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
        attribution="Tiles &copy; Esri"
      />

      {isDrawingLot &&
        (selectedProperty?.nodes ?? []).map((node, index) => (
          <CircleMarker
            key={`property-node-${selectedProperty?.id}-${index}`}
            center={[node.lat, node.lng]}
            radius={4}
            pathOptions={{ color: '#ffffff', fillColor: '#4db6e8', fillOpacity: 0.7 }}
          />
        ))}

      {isDrawingLot && draftLotNodes.length > 0 && (
        <>
          {draftLotNodes.map((node, index) => (
            <Marker
              key={`draft-lot-node-${index}`}
              position={[node.lat, node.lng]}
              icon={draftNodeIcon}
              draggable
              eventHandlers={{
                dragend: (event: any) => {
                  const latlng = event.target.getLatLng()
                  onUpdateDraftNode(index, { lat: latlng.lat, lng: latlng.lng })
                },
                contextmenu: () => onRemoveDraftNode(index),
              }}
            />
          ))}
          {draftLotNodes.length >= 3 && (
            <Polygon
              positions={orderNodesByClosestPair(draftLotNodes).map(
                (node) => [node.lat, node.lng] as [number, number],
              )}
              pathOptions={{
                color: '#9cf2a7',
                weight: 2,
                dashArray: '5 4',
                fillColor: '#9cf2a7',
                fillOpacity: 0.16,
              }}
            />
          )}
        </>
      )}

      {properties
        .filter((property) => property.nodes.length >= 3)
        .map((property) => {
          const polygons = getPolygonLayers(property.nodes)
          const isSelected = property.id === selectedPropertyId
          const isHovered = property.id === hoveredPropertyId

          return polygons.map((positions, polygonIndex) => (
            <Polygon
              key={`property-${property.id}-${polygonIndex}`}
              positions={positions}
              pathOptions={{
                color: isSelected ? '#f7b955' : isHovered ? '#7ad5ff' : '#4db6e8',
                weight: isSelected || isHovered ? 3 : 2,
                opacity: 0.95,
                fillColor: isSelected ? '#f7b955' : '#4db6e8',
                fillOpacity: isSelected ? 0.32 : isHovered ? 0.28 : 0.2,
              }}
              eventHandlers={{
                mouseover: () => setHoveredPropertyId(property.id),
                mouseout: () => setHoveredPropertyId((current) =>
                  current === property.id ? null : current,
                ),
                click: (event: any) => {
                  if (isDrawingLot && property.id === selectedPropertyId) {
                    onMapDraftNode({
                      lat: event.latlng.lat,
                      lng: event.latlng.lng,
                    })
                    return
                  }

                  onSelectProperty(property.id)
                },
              }}
              ref={(layer: any) => {
                if (layer && polygonIndex === 0) {
                  propertyPopupRefs.current[property.id] = layer
                }
              }}
            >
              {!isDrawingLot && (
                <Popup>
                  {isAdmin && editingPropertyId === property.id ? (
                    <div style={{ minWidth: '300px' }}>
                      <strong style={{ display: 'block', marginBottom: '8px' }}>{property.name}</strong>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        <input
                          type="text"
                          value={editingPropertyResponsible}
                          onChange={(e) => onPropertyChange('responsible', e.target.value)}
                          placeholder="Responsable"
                          style={{ padding: '4px', borderRadius: '4px', border: '1px solid #ccc' }}
                        />
                        <input
                          type="text"
                          value={editingPropertyCropType}
                          onChange={(e) => onPropertyChange('cropType', e.target.value)}
                          placeholder="Cultivo"
                          style={{ padding: '4px', borderRadius: '4px', border: '1px solid #ccc' }}
                        />
                        <input
                          type="number"
                          min="0"
                          value={editingPropertyWateringFrequency}
                          onChange={(e) => onPropertyChange('wateringFrequency', e.target.value)}
                          placeholder="Riegos por mes"
                          style={{ padding: '4px', borderRadius: '4px', border: '1px solid #ccc' }}
                        />
                        <textarea
                          value={editingPropertyNotes}
                          onChange={(e) => onPropertyChange('notes', e.target.value)}
                          placeholder="Descripción del predio"
                          rows={3}
                          style={{ padding: '4px', borderRadius: '4px', border: '1px solid #ccc', resize: 'vertical' }}
                        />
                        <p style={{ margin: '4px 0', fontSize: '12px', color: '#666' }}>
                          Se guarda automáticamente
                        </p>
                      </div>
                    </div>
                  ) : (
                    <div>
                      <strong>{property.name}</strong>
                      <p style={{ margin: '6px 0 0' }}>
                        {property.notes?.trim() || 'Sin descripción registrada para este predio.'}
                      </p>
                    </div>
                  )}
                </Popup>
              )}
            </Polygon>
          ))
        })}

      {properties.map((property) =>
        property.lots.map((lot) => {
          const polygons = getPolygonLayers(lot.coordinatesGeojson)

          if (polygons.length === 0) {
            return null
          }

          const isSelected = selectedNodeId === lot.id
          const belongsToSelectedProperty = property.id === selectedPropertyId

          return polygons.map((positions, polygonIndex) => (
            <Polygon
              key={`subpredio-${property.id}-${lot.id}-${polygonIndex}`}
              positions={positions}
              pathOptions={{
                color: isSelected ? '#ffd76a' : '#f7b955',
                weight: isSelected ? 4 : belongsToSelectedProperty ? 2.5 : 2,
                opacity: belongsToSelectedProperty ? 0.92 : 0.82,
                fillColor: '#f7b955',
                fillOpacity: isSelected ? 0.3 : belongsToSelectedProperty ? 0.16 : 0.1,
                dashArray: '7 5',
              }}
              eventHandlers={{
                click: (event: any) => {
                  if (isDrawingLot && property.id === selectedPropertyId) {
                    onMapDraftNode({
                      lat: event.latlng.lat,
                      lng: event.latlng.lng,
                    })
                    return
                  }

                  onSelectNode(property.id, lot.id)
                },
              }}
              ref={(layer: any) => {
                if (layer && polygonIndex === 0) {
                  nodePopupRefs.current[lot.id] = layer
                }
              }}
            >
              {!isDrawingLot && (
                <Popup>
                  {isAdmin && selectedNodeId === lot.id ? (
                    <div style={{ minWidth: '300px' }}>
                      <strong style={{ display: 'block', marginBottom: '8px' }}>{lot.name}</strong>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        <input
                          type="text"
                          value={editingNodeResponsible}
                          onChange={(e) => onNodeChange('responsible', e.target.value)}
                          placeholder="Responsable"
                          style={{ padding: '4px', borderRadius: '4px', border: '1px solid #ccc' }}
                        />
                        <input
                          type="number"
                          value={editingNodeArea}
                          onChange={(e) => onNodeChange('area', e.target.value)}
                          placeholder="Área (hectáreas)"
                          step="0.01"
                          style={{ padding: '4px', borderRadius: '4px', border: '1px solid #ccc' }}
                        />
                        <textarea
                          value={editingNodeNotes}
                          onChange={(e) => onNodeChange('notes', e.target.value)}
                          placeholder="Descripción del subpredio"
                          rows={3}
                          style={{ padding: '4px', borderRadius: '4px', border: '1px solid #ccc', resize: 'vertical' }}
                        />
                        <p style={{ margin: '4px 0', fontSize: '12px', color: '#666' }}>
                          Se guarda automáticamente
                        </p>
                      </div>
                    </div>
                  ) : (
                    <div>
                      <strong>{lot.name}</strong>
                      {lot.responsible && <p style={{ margin: '4px 0 0' }}>{lot.responsible}</p>}
                      {lot.areaHectares && (
                        <p style={{ margin: '2px 0 0', fontSize: '12px', color: '#666' }}>
                          {lot.areaHectares} ha
                        </p>
                      )}
                    </div>
                  )}
                </Popup>
              )}
            </Polygon>
          ))
        }),
      )}

    </MapContainer>
  )
}

export default App
