import { useEffect, useState } from 'react'
import { ApiError, api, clearToken, getStoredToken, IS_DEMO_MODE, storeToken } from './api/client'
import AppHeader from './components/AppHeader'
import Dashboard from './components/dashboard/Dashboard'
import LandingPage from './components/LandingPage'
import LoginPage from './components/LoginPage'

const demoUser = {
  id: 'demo-operator',
  name: 'Demo Operator',
  email: 'operator@reloop.demo',
  role: 'OPERATOR',
}

const dashboardRoles = new Set(['ADMIN', 'OPERATOR', 'RECYCLER'])

const requireDashboardRole = (profile) => {
  if (!dashboardRoles.has(profile.role)) {
    throw new ApiError('This account does not have staff dashboard access.', 403)
  }
  return profile
}

const readRoute = () => {
  const value = window.location.hash.replace(/^#\/?/, '').split('?')[0]
  return ['dashboard', 'login'].includes(value) ? value : 'home'
}

const App = () => {
  const [route, setRoute] = useState(readRoute)
  const [theme, setTheme] = useState(() => localStorage.getItem('reloop_theme') || 'dark')
  const [token, setToken] = useState(getStoredToken)
  const [user, setUser] = useState(null)
  const [authLoading, setAuthLoading] = useState(() => !IS_DEMO_MODE && Boolean(getStoredToken()))

  useEffect(() => {
    const onHashChange = () => setRoute(readRoute())
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem('reloop_theme', theme)
  }, [theme])

  useEffect(() => {
    if (IS_DEMO_MODE || !token) {
      return undefined
    }

    let active = true
    api
      .me(token)
      .then((profile) => {
        if (active) setUser(requireDashboardRole(profile))
      })
      .catch(() => {
        if (!active) return
        clearToken()
        setToken(null)
        setUser(null)
        window.location.hash = '#/login'
      })
      .finally(() => {
        if (active) setAuthLoading(false)
      })

    return () => {
      active = false
    }
  }, [token])

  const navigate = (nextRoute) => {
    window.location.hash = nextRoute === 'home' ? '#/' : `#/${nextRoute}`
  }

  const openDashboard = () => {
    if (IS_DEMO_MODE) {
      setUser(demoUser)
      navigate('dashboard')
      return
    }
    navigate(token ? 'dashboard' : 'login')
  }

  const handleLogin = async (email, password) => {
    const session = await api.login(email, password)
    const profile = requireDashboardRole(await api.me(session.access_token))
    storeToken(session.access_token)
    setToken(session.access_token)
    setUser(profile)
    navigate('dashboard')
  }

  const logout = () => {
    clearToken()
    setToken(null)
    setUser(null)
    navigate('home')
  }

  const toggleTheme = () => setTheme((current) => (current === 'dark' ? 'light' : 'dark'))

  const protectedDashboard = route === 'dashboard' && (IS_DEMO_MODE || token)

  return (
    <div className="app-shell">
      <AppHeader
        demoMode={IS_DEMO_MODE}
        onDashboard={openDashboard}
        onHome={() => navigate('home')}
        onLogout={logout}
        onThemeToggle={toggleTheme}
        theme={theme}
        user={user}
      />

      {authLoading ? (
        <main className="centered-page" aria-live="polite">
          <div className="loader" />
          <p>Restoring your secure session…</p>
        </main>
      ) : protectedDashboard ? (
        <Dashboard demoMode={IS_DEMO_MODE} onSessionExpired={logout} token={token} user={user || demoUser} />
      ) : route === 'login' && !IS_DEMO_MODE ? (
        <LoginPage onBack={() => navigate('home')} onLogin={handleLogin} />
      ) : (
        <LandingPage demoMode={IS_DEMO_MODE} onDashboard={openDashboard} />
      )}
    </div>
  )
}

export default App
