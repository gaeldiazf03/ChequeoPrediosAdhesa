import { useEffect, useState, type FormEvent } from 'react'
import {
  GoogleMap,
  MarkerF,
  PolygonF,
  useJsApiLoader,
} from '@react-google-maps/api'
import './App.css'

type Role = 'admin' | 'manager' | 'viewer'

type Account = {
  id: string
  name: string
  email: string
  password: string
  role: Role
  active: boolean
}

type NodePoint = {
  lat: number
  lng: number
}

type Property = {
  id: string
  name: string
  region: string
  notes: string
  nodes: NodePoint[]
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

const STORAGE_KEYS = {
  accounts: 'chequeo-predios.accounts',
  properties: 'chequeo-predios.properties',
  session: 'chequeo-predios.session',
}

const MAP_CENTER = { lat: 21.4, lng: -98.6 }
const GOOGLE_MAPS_API_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY as
  | string
  | undefined

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

const initialAccounts: Account[] = [
  {
    id: 'admin-1',
    name: 'Administrador general',
    email: 'admin@chequeopredios.mx',
    password: 'Admin123!',
    role: 'admin',
    active: true,
  },
  {
    id: 'manager-1',
    name: 'Coordinación Huasteca',
    email: 'huasteca@chequeopredios.mx',
    password: 'Huasteca123!',
    role: 'manager',
    active: true,
  },
  {
    id: 'viewer-1',
    name: 'Consulta predial',
    email: 'consulta@chequeopredios.mx',
    password: 'Consulta123!',
    role: 'viewer',
    active: true,
  },
]

const initialProperties: Property[] = [
  {
    id: 'predio-rio-verde',
    name: 'Predio Río Verde',
    region: 'Huasteca potosina',
    notes:
      'Base inicial para delimitar el contorno. Se puede mover cada nodo o agregar nuevos puntos desde el mapa.',
    nodes: [
      { lat: 21.48, lng: -98.8 },
      { lat: 21.62, lng: -98.42 },
      { lat: 21.22, lng: -98.16 },
      { lat: 21.02, lng: -98.52 },
      { lat: 21.18, lng: -98.94 },
    ],
  },
  {
    id: 'predio-emerald',
    name: 'Predio Las Cuencas',
    region: 'Huasteca veracruzana',
    notes: 'Plantilla secundaria para futuras expansiones del sistema.',
    nodes: [
      { lat: 21.74, lng: -98.68 },
      { lat: 21.82, lng: -98.28 },
      { lat: 21.56, lng: -98.18 },
      { lat: 21.42, lng: -98.53 },
    ],
  },
]

function readStorage<T>(key: string, fallback: T): T {
  if (typeof window === 'undefined') {
    return fallback
  }

  try {
    const rawValue = window.localStorage.getItem(key)
    return rawValue ? (JSON.parse(rawValue) as T) : fallback
  } catch {
    return fallback
  }
}

function writeStorage<T>(key: string, value: T) {
  window.localStorage.setItem(key, JSON.stringify(value))
}

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

function cloneNodes(nodes: NodePoint[]) {
  return nodes.map((node) => ({ ...node }))
}

function formatCoordinate(value: number) {
  return value.toFixed(5)
}

function App() {
  const [themeLoaded, setThemeLoaded] = useState(false)
  const [accounts, setAccounts] = useState<Account[]>(() =>
    readStorage(STORAGE_KEYS.accounts, initialAccounts),
  )
  const [properties, setProperties] = useState<Property[]>(() =>
    readStorage(STORAGE_KEYS.properties, initialProperties),
  )
  const [session, setSession] = useState<Account | null>(() =>
    readStorage<Account | null>(STORAGE_KEYS.session, null),
  )
  const [loginEmail, setLoginEmail] = useState('admin@chequeopredios.mx')
  const [loginPassword, setLoginPassword] = useState('Admin123!')
  const [loginMessage, setLoginMessage] = useState('')
  const [selectedPropertyId, setSelectedPropertyId] = useState(
    properties[0]?.id ?? '',
  )
  const [newAccount, setNewAccount] = useState({
    name: '',
    email: '',
    password: '',
    role: 'viewer' as Role,
  })

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

  useEffect(() => {
    writeStorage(STORAGE_KEYS.accounts, accounts)
  }, [accounts])

  useEffect(() => {
    writeStorage(STORAGE_KEYS.properties, properties)
  }, [properties])

  useEffect(() => {
    if (session) {
      writeStorage(STORAGE_KEYS.session, session)
    } else {
      window.localStorage.removeItem(STORAGE_KEYS.session)
    }
  }, [session])

  useEffect(() => {
    if (!selectedPropertyId && properties[0]) {
      setSelectedPropertyId(properties[0].id)
    }
  }, [properties, selectedPropertyId])

  const activeProperty =
    properties.find((property) => property.id === selectedPropertyId) ??
    properties[0]

  const isAdmin = session?.role === 'admin'
  const canEditMap = Boolean(session && session.active && session.role !== 'viewer')

  function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    const match = accounts.find(
      (account) =>
        account.email.toLowerCase() === loginEmail.toLowerCase() &&
        account.password === loginPassword,
    )

    if (!match) {
      setLoginMessage('Credenciales inválidas. Verifica el correo y la contraseña.')
      return
    }

    if (!match.active) {
      setLoginMessage('La cuenta está desactivada. Solicita acceso al administrador.')
      return
    }

    setSession(match)
    setLoginMessage('')
  }

  function handleLogout() {
    setSession(null)
  }

  function handleCreateAccount(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    if (!isAdmin) {
      return
    }

    const emailExists = accounts.some(
      (account) => account.email.toLowerCase() === newAccount.email.toLowerCase(),
    )

    if (emailExists) {
      return
    }

    const account: Account = {
      id: crypto.randomUUID(),
      name: newAccount.name.trim(),
      email: newAccount.email.trim().toLowerCase(),
      password: newAccount.password,
      role: newAccount.role,
      active: true,
    }

    setAccounts((currentAccounts) => [account, ...currentAccounts])
    setNewAccount({ name: '', email: '', password: '', role: 'viewer' })
  }

  function handleUpdateAccount(id: string, patch: Partial<Account>) {
    setAccounts((currentAccounts) =>
      currentAccounts.map((account) =>
        account.id === id ? { ...account, ...patch } : account,
      ),
    )

    if (session?.id === id && patch.active === false) {
      setSession(null)
    }
  }

  function handleDeleteAccount(id: string) {
    if (!isAdmin) {
      return
    }

    setAccounts((currentAccounts) =>
      currentAccounts.filter((account) => account.id !== id),
    )

    if (session?.id === id) {
      setSession(null)
    }
  }

  function handleUpdatePropertyNodes(propertyId: string, nodes: NodePoint[]) {
    setProperties((currentProperties) =>
      currentProperties.map((property) =>
        property.id === propertyId ? { ...property, nodes: cloneNodes(nodes) } : property,
      ),
    )
  }

  function handleCreateNodeFromCenter() {
    if (!activeProperty) {
      return
    }

    const newNode = { ...MAP_CENTER }
    handleUpdatePropertyNodes(activeProperty.id, [...activeProperty.nodes, newNode])
  }

  function handleRemoveLastNode() {
    if (!activeProperty || activeProperty.nodes.length <= 3) {
      return
    }

    handleUpdatePropertyNodes(
      activeProperty.id,
      activeProperty.nodes.slice(0, activeProperty.nodes.length - 1),
    )
  }

  function handleUpdateNode(propertyId: string, nodeIndex: number, patch: Partial<NodePoint>) {
    const property = properties.find((item) => item.id === propertyId)

    if (!property) {
      return
    }

    const nextNodes = property.nodes.map((node, index) =>
      index === nodeIndex ? { ...node, ...patch } : node,
    )

    handleUpdatePropertyNodes(propertyId, nextNodes)
  }

  function handleAddNodeFromMap(point: NodePoint) {
    if (!activeProperty || !canEditMap) {
      return
    }

    handleUpdatePropertyNodes(activeProperty.id, [...activeProperty.nodes, point])
  }

  function handleMoveNode(propertyId: string, nodeIndex: number, point: NodePoint) {
    const property = properties.find((item) => item.id === propertyId)

    if (!property) {
      return
    }

    const nextNodes = property.nodes.map((node, index) =>
      index === nodeIndex ? point : node,
    )

    handleUpdatePropertyNodes(propertyId, nextNodes)
  }

  if (!themeLoaded) {
    return (
      <main className="loading-shell">
        <p>Preparando la configuración visual y el panel de administración...</p>
      </main>
    )
  }

  if (!session) {
    return (
      <main className="auth-page">
        <section className="hero-panel surface-card">
          <div className="hero-panel__label">Chequeo Predios</div>
          <h1>Administración predial para México y la Huasteca</h1>
          <p>
            Base escalable con login, administración de cuentas y edición de
            polígonos para predios. Diseñado para crecer hacia un backend real
            cuando definas la siguiente fase.
          </p>
          <div className="hero-panel__stats">
            <article>
              <strong>{accounts.length}</strong>
              <span>cuentas cargadas</span>
            </article>
            <article>
              <strong>{properties.length}</strong>
              <span>predios iniciales</span>
            </article>
            <article>
              <strong>{initialProperties[0].nodes.length}</strong>
              <span>nodos base</span>
            </article>
          </div>
        </section>

        <section className="surface-card auth-card">
          <div className="section-heading">
            <span>Acceso seguro</span>
            <h2>Inicia sesión</h2>
          </div>
          <form className="auth-form" onSubmit={handleLogin}>
            <label>
              <span>Correo</span>
              <input
                type="email"
                value={loginEmail}
                onChange={(event) => setLoginEmail(event.target.value)}
                placeholder="admin@chequeopredios.mx"
                autoComplete="email"
              />
            </label>
            <label>
              <span>Contraseña</span>
              <input
                type="password"
                value={loginPassword}
                onChange={(event) => setLoginPassword(event.target.value)}
                placeholder="Admin123!"
                autoComplete="current-password"
              />
            </label>

            {loginMessage ? <p className="form-message">{loginMessage}</p> : null}

            <button type="submit" className="primary-button">
              Entrar al panel
            </button>
          </form>

          <div className="credential-card">
            <p className="credential-card__label">Cuenta demo</p>
            <strong>admin@chequeopredios.mx</strong>
            <span>Contraseña: Admin123!</span>
          </div>
        </section>
      </main>
    )
  }

  return (
    <main className="dashboard-shell">
      <aside className="sidebar surface-card">
        <div className="brand-block">
          <div>
            <p className="brand-block__eyebrow">Chequeo Predios</p>
            <h1>Panel administrativo</h1>
          </div>
          <button className="ghost-button" type="button" onClick={handleLogout}>
            Salir
          </button>
        </div>

        <div className="session-card">
          <span>Sesión activa</span>
          <strong>{session.name}</strong>
          <p>
            {session.email} · {session.role}
          </p>
        </div>

        <div className="metric-grid">
          <article>
            <strong>{accounts.length}</strong>
            <span>cuentas</span>
          </article>
          <article>
            <strong>{properties.length}</strong>
            <span>predios</span>
          </article>
          <article>
            <strong>{activeProperty?.nodes.length ?? 0}</strong>
            <span>nodos</span>
          </article>
          <article>
            <strong>{canEditMap ? 'Activo' : 'Vista'}</strong>
            <span>modo mapa</span>
          </article>
        </div>

        <section className="surface-card sidebar-section">
          <div className="section-heading">
            <span>Predio actual</span>
            <h2>Huasteca</h2>
          </div>

          <select
            value={selectedPropertyId}
            onChange={(event) => setSelectedPropertyId(event.target.value)}
          >
            {properties.map((property) => (
              <option key={property.id} value={property.id}>
                {property.name}
              </option>
            ))}
          </select>

          <div className="property-summary">
            <strong>{activeProperty?.region}</strong>
            <p>{activeProperty?.notes}</p>
          </div>
        </section>

        <section className="surface-card sidebar-section">
          <div className="section-heading">
            <span>Nodos</span>
            <h2>Edición rápida</h2>
          </div>

          <div className="editor-actions">
            <button
              type="button"
              className="secondary-button"
              onClick={handleCreateNodeFromCenter}
              disabled={!canEditMap}
            >
              Agregar nodo
            </button>
            <button
              type="button"
              className="secondary-button"
              onClick={handleRemoveLastNode}
              disabled={!canEditMap || !activeProperty || activeProperty.nodes.length <= 3}
            >
              Quitar nodo
            </button>
          </div>

          <div className="node-list">
            {activeProperty?.nodes.map((node, nodeIndex) => (
              <div className="node-item" key={`${activeProperty.id}-${nodeIndex}`}>
                <div className="node-item__header">
                  <strong>Nodo {nodeIndex + 1}</strong>
                  <span>
                    {formatCoordinate(node.lat)}, {formatCoordinate(node.lng)}
                  </span>
                </div>
                <div className="node-item__inputs">
                  <label>
                    <span>Latitud</span>
                    <input
                      type="number"
                      step="0.00001"
                      value={node.lat}
                      disabled={!canEditMap}
                      onChange={(event) =>
                        handleUpdateNode(activeProperty.id, nodeIndex, {
                          lat: Number(event.target.value),
                        })
                      }
                    />
                  </label>
                  <label>
                    <span>Longitud</span>
                    <input
                      type="number"
                      step="0.00001"
                      value={node.lng}
                      disabled={!canEditMap}
                      onChange={(event) =>
                        handleUpdateNode(activeProperty.id, nodeIndex, {
                          lng: Number(event.target.value),
                        })
                      }
                    />
                  </label>
                </div>
              </div>
            ))}
          </div>
        </section>

        {isAdmin ? (
          <section className="surface-card sidebar-section">
            <div className="section-heading">
              <span>Usuarios</span>
              <h2>Administrar cuentas</h2>
            </div>

            <form className="account-form" onSubmit={handleCreateAccount}>
              <label>
                <span>Nombre</span>
                <input
                  value={newAccount.name}
                  onChange={(event) =>
                    setNewAccount((current) => ({
                      ...current,
                      name: event.target.value,
                    }))
                  }
                  placeholder="Nueva cuenta"
                />
              </label>
              <label>
                <span>Correo</span>
                <input
                  type="email"
                  value={newAccount.email}
                  onChange={(event) =>
                    setNewAccount((current) => ({
                      ...current,
                      email: event.target.value,
                    }))
                  }
                  placeholder="usuario@chequeopredios.mx"
                />
              </label>
              <label>
                <span>Contraseña</span>
                <input
                  type="password"
                  value={newAccount.password}
                  onChange={(event) =>
                    setNewAccount((current) => ({
                      ...current,
                      password: event.target.value,
                    }))
                  }
                  placeholder="Define acceso"
                />
              </label>
              <label>
                <span>Rol</span>
                <select
                  value={newAccount.role}
                  onChange={(event) =>
                    setNewAccount((current) => ({
                      ...current,
                      role: event.target.value as Role,
                    }))
                  }
                >
                  <option value="viewer">viewer</option>
                  <option value="manager">manager</option>
                  <option value="admin">admin</option>
                </select>
              </label>
              <button type="submit" className="primary-button">
                Crear cuenta
              </button>
            </form>

            <div className="account-list">
              {accounts.map((account) => (
                <div className="account-row" key={account.id}>
                  <div>
                    <strong>{account.name}</strong>
                    <p>{account.email}</p>
                  </div>
                  <div className="account-row__actions">
                    <select
                      value={account.role}
                      onChange={(event) =>
                        handleUpdateAccount(account.id, {
                          role: event.target.value as Role,
                        })
                      }
                    >
                      <option value="viewer">viewer</option>
                      <option value="manager">manager</option>
                      <option value="admin">admin</option>
                    </select>
                    <button
                      type="button"
                      className="secondary-button"
                      onClick={() =>
                        handleUpdateAccount(account.id, { active: !account.active })
                      }
                    >
                      {account.active ? 'Desactivar' : 'Activar'}
                    </button>
                    <button
                      type="button"
                      className="danger-button"
                      onClick={() => handleDeleteAccount(account.id)}
                    >
                      Eliminar
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </section>
        ) : null}
      </aside>

      <section className="main-panel">
        <header className="surface-card page-header">
          <div>
            <span className="page-header__eyebrow">Visualizador</span>
            <h2>Mapa de México con foco en la Huasteca</h2>
          </div>
          <p>
            El contorno del predio se puede mover, ampliar o reducir desde el
            panel lateral o directamente sobre el mapa.
          </p>
        </header>

        <section className="surface-card map-card">
          {GOOGLE_MAPS_API_KEY ? (
            <EditableMap
              apiKey={GOOGLE_MAPS_API_KEY}
              property={activeProperty}
              canEdit={canEditMap}
              onAddNode={handleAddNodeFromMap}
              onMoveNode={handleMoveNode}
            />
          ) : (
            <div className="map-placeholder">
              <strong>Google Maps pendiente de configuración</strong>
              <p>
                Agrega la variable de entorno <span>VITE_GOOGLE_MAPS_API_KEY</span>{' '}
                para cargar el mapa interactivo. La estructura del editor ya está
                lista y el contorno del predio se conserva en la aplicación.
              </p>
              <div className="map-placeholder__meta">
                <span>Centro inicial: México / Huasteca</span>
                <span>
                  Nodos actuales: {activeProperty?.nodes.length ?? 0}
                </span>
              </div>
            </div>
          )}
        </section>
      </section>
    </main>
  )
}

function EditableMap({
  apiKey,
  property,
  canEdit,
  onAddNode,
  onMoveNode,
}: {
  apiKey: string
  property?: Property
  canEdit: boolean
  onAddNode: (point: NodePoint) => void
  onMoveNode: (propertyId: string, nodeIndex: number, point: NodePoint) => void
}) {
  const { isLoaded } = useJsApiLoader({
    googleMapsApiKey: apiKey,
    id: 'chequeo-predios-google-maps',
  })

  if (!property) {
    return <div className="map-placeholder">No hay predio seleccionado.</div>
  }

  if (!isLoaded) {
    return <div className="map-placeholder">Cargando Google Maps...</div>
  }

  return (
    <GoogleMap
      mapContainerClassName="google-map"
      center={MAP_CENTER}
      zoom={7}
      onClick={(event) => {
        if (!canEdit || !event.latLng) {
          return
        }

        onAddNode({
          lat: event.latLng.lat(),
          lng: event.latLng.lng(),
        })
      }}
      options={{
        disableDefaultUI: true,
        clickableIcons: false,
        gestureHandling: 'greedy',
        mapTypeControl: true,
        mapTypeControlOptions: {
          position: google.maps.ControlPosition.TOP_RIGHT,
        },
        streetViewControl: false,
        fullscreenControl: false,
        zoomControl: true,
        styles: [
          {
            elementType: 'geometry',
            stylers: [{ color: '#10213a' }],
          },
          {
            elementType: 'labels.text.fill',
            stylers: [{ color: '#d8e2f4' }],
          },
          {
            elementType: 'labels.text.stroke',
            stylers: [{ color: '#08111f' }],
          },
          {
            featureType: 'water',
            stylers: [{ color: '#14324f' }],
          },
          {
            featureType: 'poi',
            stylers: [{ visibility: 'off' }],
          },
        ],
      }}
    >
      <PolygonF
        paths={property.nodes}
        options={{
          strokeColor: '#f7b955',
          strokeOpacity: 0.95,
          strokeWeight: 3,
          fillColor: '#f7b955',
          fillOpacity: 0.18,
          clickable: false,
          editable: false,
          draggable: false,
        }}
      />

      {property.nodes.map((node, nodeIndex) => (
        <MarkerF
          key={`${property.id}-${nodeIndex}`}
          position={node}
          draggable={canEdit}
          onDragEnd={(event) => {
            if (!canEdit || !event.latLng) {
              return
            }

            onMoveNode(property.id, nodeIndex, {
              lat: event.latLng.lat(),
              lng: event.latLng.lng(),
            })
          }}
        />
      ))}
    </GoogleMap>
  )
}

export default App
