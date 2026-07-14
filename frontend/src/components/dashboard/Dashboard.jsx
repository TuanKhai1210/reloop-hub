import { useEffect, useState } from 'react'
import {
  ArcElement,
  CategoryScale,
  Chart as ChartJS,
  Filler,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
} from 'chart.js'
import { ApiError, api, createHubSocket } from '../../api/client'
import CommunityPanel from './CommunityPanel'
import EsgPanel from './EsgPanel'
import HubsPanel from './HubsPanel'
import OverviewPanel from './OverviewPanel'
import QualityPanel from './QualityPanel'
import RoutesPanel from './RoutesPanel'
import TraceabilityPanel from './TraceabilityPanel'
import StatePanel from '../ui/StatePanel'

ChartJS.register(ArcElement, CategoryScale, Filler, Legend, LinearScale, LineElement, PointElement, Tooltip)

const tabs = [
  { id: 'overview', label: 'Overview' },
  { id: 'hubs', label: 'Smart Hubs' },
  { id: 'routes', label: 'Routes' },
  { id: 'quality', label: 'Feedstock quality' },
  { id: 'community', label: 'People & rewards' },
  { id: 'traceability', label: 'Traceability' },
  { id: 'esg', label: 'ESG report' },
]

const periods = ['day', 'week', 'month']

const Dashboard = ({ demoMode, onSessionExpired, token, user }) => {
  const [activeTab, setActiveTab] = useState('overview')
  const [period, setPeriod] = useState('day')
  const [reloadKey, setReloadKey] = useState(0)
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [connection, setConnection] = useState(demoMode ? 'SIMULATED' : 'CONNECTING')
  const [selectedHub, setSelectedHub] = useState(null)
  const [telemetry, setTelemetry] = useState([])
  const [loadingTelemetry, setLoadingTelemetry] = useState(false)

  useEffect(() => {
    let active = true
    Promise.all([
      api.dashboardSummary(period, token),
      api.hubs(token),
      api.routes(token),
      api.deposits(token),
      api.esgReport(period, token),
      ['ADMIN', 'OPERATOR'].includes(user.role) ? api.users(token) : Promise.resolve([]),
      api.vouchers(token),
    ])
      .then(([summary, hubs, routes, deposits, esg, users, vouchers]) => {
        if (!active) return
        setData({ summary, hubs, routes, deposits, esg, users, vouchers })
        setError('')
      })
      .catch((requestError) => {
        if (!active) return
        if (requestError instanceof ApiError && requestError.status === 401) {
          onSessionExpired()
          return
        }
        setError(requestError.message || 'Dashboard data could not be loaded.')
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => {
      active = false
    }
  }, [onSessionExpired, period, reloadKey, token, user.role])

  useEffect(() => {
    const socket = createHubSocket(token)
    if (!socket) return undefined

    socket.addEventListener('open', () => setConnection('LIVE'))
    socket.addEventListener('close', () => setConnection('DISCONNECTED'))
    socket.addEventListener('error', () => setConnection('DISCONNECTED'))
    socket.addEventListener('message', (message) => {
      try {
        const event = JSON.parse(message.data)
        if (event.event !== 'hub.telemetry') return
        setData((current) => {
          if (!current) return current
          return {
            ...current,
            hubs: current.hubs.map((hub) => hub.code === event.data.hub_code ? { ...hub, fill_level: event.data.fill_level, status: event.data.status, last_seen_at: new Date().toISOString() } : hub),
          }
        })
      } catch {
        // Ignore non-JSON heartbeat messages from the socket.
      }
    })

    return () => socket.close()
  }, [token])

  const changePeriod = (nextPeriod) => {
    if (nextPeriod === period) return
    setLoading(true)
    setSelectedHub(null)
    setTelemetry([])
    setPeriod(nextPeriod)
  }

  const retry = () => {
    setError('')
    setLoading(true)
    setReloadKey((value) => value + 1)
  }

  const selectHub = async (hub) => {
    setSelectedHub(hub)
    setLoadingTelemetry(true)
    try {
      setTelemetry(await api.telemetry(hub.code, hub.id, period, token))
    } catch (requestError) {
      setTelemetry([])
      setError(requestError.message || 'Hub telemetry could not be loaded.')
    } finally {
      setLoadingTelemetry(false)
    }
  }

  const lookupTraceability = (traceCode) => api.traceability(traceCode, token)

  const activeTabLabel = tabs.find((tab) => tab.id === activeTab)?.label

  return (
    <main className="dashboard-page">
      <section className="dashboard-topbar">
        <div>
          <span className="eyebrow">Operations workspace</span>
          <h1>{activeTabLabel}</h1>
          <p>Welcome, {user.name}. Monitor verified PET/HDPE material from campus return to recycler receipt.</p>
        </div>
        <div className="dashboard-controls">
          <span className={`connection-pill connection-${connection.toLowerCase()}`}><span />{connection}</span>
          <div className="period-switcher" aria-label="Reporting period">
            {periods.map((item) => <button className={period === item ? 'active' : ''} type="button" key={item} onClick={() => changePeriod(item)}>{item}</button>)}
          </div>
        </div>
      </section>

      {demoMode && (
        <div className="data-banner">
          <strong>Prototype sample data</strong>
          <span>Use this mode to demonstrate flows without a backend. Set VITE_DEMO_MODE=false for authenticated live data.</span>
        </div>
      )}

      <nav className="dashboard-tabs" aria-label="Dashboard sections">
        {tabs.map((tab) => <button key={tab.id} type="button" className={activeTab === tab.id ? 'active' : ''} onClick={() => setActiveTab(tab.id)}>{tab.label}</button>)}
      </nav>

      {error && <StatePanel tone="danger" title="Unable to refresh dashboard" message={error} action={retry} actionLabel="Try again" />}

      {loading || !data ? (
        <div className="dashboard-loading" aria-live="polite"><div className="loader" /><strong>Preparing {period} view…</strong><span>Loading verified material and logistics data.</span></div>
      ) : (
        <div className="dashboard-content">
          {activeTab === 'overview' && <OverviewPanel hubs={data.hubs} summary={data.summary} />}
          {activeTab === 'hubs' && <HubsPanel hubs={data.hubs} loadingTelemetry={loadingTelemetry} onSelectHub={selectHub} selectedHub={selectedHub} telemetry={telemetry} />}
          {activeTab === 'routes' && <RoutesPanel hubs={data.hubs} routes={data.routes} />}
          {activeTab === 'quality' && <QualityPanel deposits={data.deposits} summary={data.summary} />}
          {activeTab === 'community' && <CommunityPanel summary={data.summary} users={data.users} vouchers={data.vouchers} />}
          {activeTab === 'traceability' && <TraceabilityPanel demoMode={demoMode} onLookup={lookupTraceability} />}
          {activeTab === 'esg' && <EsgPanel demoMode={demoMode} report={data.esg} />}
        </div>
      )}
    </main>
  )
}

export default Dashboard
