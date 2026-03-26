import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { fetchApi } from '../api'
import StatsCard from '../components/StatsCard'

function fmt(val, decimals = 2) {
  if (val == null) return '--'
  return Number(val).toFixed(decimals)
}

function ratingClass(val) {
  if (val == null) return ''
  if (val >= 1.1) return 'rating-high'
  if (val >= 0.95) return 'rating-mid'
  return 'rating-low'
}

export default function Dashboard() {
  const [stats, setStats] = useState(null)
  const [events, setEvents] = useState([])
  const [topPlayers, setTopPlayers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    async function load() {
      try {
        const [s, e, p] = await Promise.all([
          fetchApi('/stats'),
          fetchApi('/events'),
          fetchApi('/players?sort_by=rating_2_0&order=desc&limit=10'),
        ])
        setStats(s)
        setEvents(e.slice(0, 5))
        setTopPlayers(Array.isArray(p) ? p : (p.players || p.data || []))
      } catch (err) {
        setError(err.message)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  if (loading) return <div className="loading"><span className="loading-spinner"></span>Loading dashboard...</div>
  if (error) return <div className="error-message">Failed to load: {error}</div>

  return (
    <div>
      <div className="page-header">
        <h1>CS2 Statistics Dashboard</h1>
        <p>Overview of all scraped HLTV data</p>
      </div>

      <div className="stats-grid">
        <StatsCard value={stats?.events ?? 0} label="Events" accent="orange" />
        <StatsCard value={stats?.teams ?? 0} label="Teams" accent="blue" />
        <StatsCard value={stats?.players ?? 0} label="Players" accent="green" />
        <StatsCard value={stats?.matches ?? 0} label="Matches" accent="red" />
        <StatsCard value={stats?.maps ?? 0} label="Maps" />
        <StatsCard value={stats?.vetos ?? 0} label="Vetos" />
        <StatsCard value={stats?.player_stats ?? 0} label="Player Stats" />
      </div>

      <div className="dashboard-grid">
        <div className="dashboard-section">
          <div className="section-header">
            <h2>Recent Events</h2>
            <Link to="/events" className="view-all-link">View all</Link>
          </div>
          {events.length === 0 ? (
            <p style={{ color: 'var(--text-muted)' }}>No events yet.</p>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Event</th>
                  <th>Location</th>
                  <th className="numeric">Prize</th>
                </tr>
              </thead>
              <tbody>
                {events.map(e => (
                  <tr key={e.id}>
                    <td><Link to={`/events/${e.id}`}>{e.name}</Link></td>
                    <td>{e.location || '--'}</td>
                    <td className="numeric">{e.prize_pool || '--'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="dashboard-section">
          <div className="section-header">
            <h2>Top Players by Rating</h2>
            <Link to="/players" className="view-all-link">View all</Link>
          </div>
          {topPlayers.length === 0 ? (
            <p style={{ color: 'var(--text-muted)' }}>No player data yet.</p>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Player</th>
                  <th className="numeric">Rating</th>
                  <th className="numeric">K/D</th>
                  <th className="numeric">ADR</th>
                </tr>
              </thead>
              <tbody>
                {topPlayers.map((p, i) => (
                  <tr key={p.id}>
                    <td style={{ color: 'var(--text-muted)' }}>{i + 1}</td>
                    <td><Link to={`/players/${p.id}`}>{p.nickname}</Link></td>
                    <td className={`numeric ${ratingClass(p.rating_2_0)}`}>{fmt(p.rating_2_0)}</td>
                    <td className="numeric">{fmt(p.kd_ratio)}</td>
                    <td className="numeric">{fmt(p.adr, 1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
}
