import { Outlet, NavLink, useLocation } from 'react-router-dom'

const navItems = [
  { path: '/', label: 'Dashboard', icon: '\u2302' },
  { path: '/events', label: 'Events', icon: '\u2605' },
  { path: '/teams', label: 'Teams', icon: '\u2691' },
  { path: '/players', label: 'Players', icon: '\u263A' },
  { path: '/matches', label: 'Matches', icon: '\u2694' },
]

function getPageTitle(pathname) {
  if (pathname === '/') return 'Dashboard'
  const segment = pathname.split('/')[1]
  if (!segment) return 'Dashboard'
  return segment.charAt(0).toUpperCase() + segment.slice(1)
}

export default function Layout() {
  const location = useLocation()
  const pageTitle = getPageTitle(location.pathname)

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <h1>HLTV <span className="brand-accent">Stats</span></h1>
        </div>
        <nav className="sidebar-nav">
          {navItems.map(item => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === '/'}
              className={({ isActive }) => isActive ? 'active' : ''}
            >
              <span className="nav-icon">{item.icon}</span>
              <span className="nav-label">{item.label}</span>
            </NavLink>
          ))}
        </nav>
      </aside>
      <div className="main-content">
        <div className="navbar">
          <span className="navbar-title">{pageTitle}</span>
        </div>
        <div className="page-content">
          <Outlet />
        </div>
      </div>
    </div>
  )
}
