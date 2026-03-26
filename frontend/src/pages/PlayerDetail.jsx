import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { fetchApi } from '../api'

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

function formatDate(dateStr) {
  if (!dateStr) return '--'
  const d = new Date(dateStr)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

const statCards = [
  { key: 'rating_2_0', label: 'Rating 2.0', fmt: v => fmt(v) },
  { key: 'kd_ratio', label: 'K/D Ratio', fmt: v => fmt(v) },
  { key: 'adr', label: 'ADR', fmt: v => fmt(v, 1) },
  { key: 'kast', label: 'KAST', fmt: v => v != null ? fmt(v, 1) + '%' : '--' },
  { key: 'impact', label: 'Impact', fmt: v => fmt(v) },
  { key: 'kpr', label: 'KPR', fmt: v => fmt(v) },
  { key: 'headshot_percentage', label: 'HS%', fmt: v => v != null ? fmt(v, 1) + '%' : '--' },
  { key: 'total_kills', label: 'Total Kills', fmt: v => v != null ? v.toLocaleString() : '--' },
  { key: 'total_deaths', label: 'Total Deaths', fmt: v => v != null ? v.toLocaleString() : '--' },
  { key: 'total_maps', label: 'Total Maps', fmt: v => v != null ? v.toLocaleString() : '--' },
]

export default function PlayerDetail() {
  const { id } = useParams()
  const [player, setPlayer] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    setLoading(true)
    fetchApi(`/players/${id}`)
      .then(data => setPlayer(data))
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) return <div className="loading"><span className="loading-spinner"></span>Loading player...</div>
  if (error) return <div className="error-message">Failed to load player: {error}</div>
  if (!player) return <div className="empty-state"><p>Player not found.</p></div>

  const matchStats = player.match_stats || []

  return (
    <div>
      <div className="player-header">
        <div className="player-info">
          <h1>{player.nickname}</h1>
          {player.real_name && <div className="player-real-name">{player.real_name}</div>}
          <div className="player-meta">
            {player.country && <span>{player.country}</span>}
            {player.age && <span>Age: {player.age}</span>}
          </div>
        </div>
      </div>

      <div className="section-header">
        <h2 className="section-title">Career Statistics</h2>
      </div>
      <div className="player-stats-grid">
        {statCards.map(s => (
          <div className="player-stat" key={s.key}>
            <div className="stat-value" style={s.key === 'rating_2_0' ? {} : {}}>
              <span className={s.key === 'rating_2_0' ? ratingClass(player[s.key]) : ''}>
                {s.fmt(player[s.key])}
              </span>
            </div>
            <div className="stat-label">{s.label}</div>
          </div>
        ))}
      </div>

      <div className="section-header" style={{ marginTop: 32 }}>
        <h2 className="section-title">Match Performance ({matchStats.length})</h2>
      </div>
      {matchStats.length === 0 ? (
        <p style={{ color: 'var(--text-muted)' }}>No per-match stats available.</p>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Event</th>
              <th>Map</th>
              <th className="numeric">K</th>
              <th className="numeric">D</th>
              <th className="numeric">A</th>
              <th className="numeric">HS</th>
              <th className="numeric">ADR</th>
              <th className="numeric">KAST</th>
              <th className="numeric">Rating</th>
            </tr>
          </thead>
          <tbody>
            {matchStats.map((s, i) => (
              <tr key={i}>
                <td>{s.event_name || '--'}</td>
                <td>
                  {s.match_id ? (
                    <Link to={`/matches/${s.match_id}`}>{s.map_name || '--'}</Link>
                  ) : (
                    s.map_name || '--'
                  )}
                </td>
                <td className="numeric">{s.kills ?? '--'}</td>
                <td className="numeric">{s.deaths ?? '--'}</td>
                <td className="numeric">{s.assists ?? '--'}</td>
                <td className="numeric">{s.headshots ?? '--'}</td>
                <td className="numeric">{fmt(s.adr, 1)}</td>
                <td className="numeric">{s.kast != null ? fmt(s.kast, 1) + '%' : '--'}</td>
                <td className={`numeric ${ratingClass(s.rating)}`}>{fmt(s.rating)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
