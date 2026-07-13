import logo from '../assets/logo-100x100.png'

const AppHeader = ({ demoMode, onDashboard, onHome, onLogout, onThemeToggle, theme, user }) => (
  <header className="site-header">
    <button className="brand" type="button" onClick={onHome} aria-label="Go to ReLoop Hub home">
      <img src={logo} alt="" />
      <span>
        <strong>ReLoop</strong>
        <small>Smart reverse logistics</small>
      </span>
    </button>

    <div className="header-actions">
      {demoMode && <span className="mode-pill">Demo data</span>}
      {user && (
        <span className="user-chip">
          <strong>{user.name}</strong>
          <small>{user.role}</small>
        </span>
      )}
      <button className="icon-button" type="button" onClick={onThemeToggle} aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}>
        {theme === 'dark' ? '☀' : '☾'}
      </button>
      {user ? (
        <button className="button button-ghost button-small" type="button" onClick={onLogout}>
          Log out
        </button>
      ) : (
        <button className="button button-primary button-small" type="button" onClick={onDashboard}>
          {demoMode ? 'Open prototype' : 'Staff login'}
        </button>
      )}
    </div>
  </header>
)

export default AppHeader
