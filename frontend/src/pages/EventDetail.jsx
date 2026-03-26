import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { fetchApi } from '../api'
import MatchCard from '../components/MatchCard'

function formatDate(dateStr) {
  if (!dateStr) return '--'
  const d = new Date(dateStr)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

function placementClass(p) {
  if (!p) return ''
  const s = String(p).toLowerCase()
  if (s === '1' || s === '1st') return 'placement-1st'
  if (s === '2' || s === '2nd') return 'placement-2nd'
  if (s === '3' || s === '3rd' || s === '3-4' || s === '3rd-4th') return 'placement-3rd'
  return ''
}

export default function EventDetail() {
  const { id } = useParams()
  const [event, setEvent] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    setLoading(true)
    fetchApi(`/events/${id}`)
      .then(data => setEvent(data))
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) return <div className="loading"><span className="loading-spinner"></span>Loading event...</div>
  if (error) return <div className="error-message">Failed to load event: {error}</div>
  if (!event) return <div className="empty-state"><p>Event not found.</p></div>

  const teams = event.teams || []
  const matches = event.matches || []

  return (
    <div>
      <div className="event-header">
        <h1>{event.name}</h1>
        <div className="event-meta">
          <span className="event-meta-item">
            <span className="meta-icon">&#128205;</span> {event.location || '--'}
          </span>
          <span className="event-meta-item">
            <span className="meta-icon">&#128176;</span> {event.prize_pool || '--'}
          </span>
          <span className="event-meta-item">
            <span className="meta-icon">&#128197;</span>
            {formatDate(event.start_date)} - {formatDate(event.end_date)}
          </span>
        </div>
      </div>

      <div className="section-header">
        <h2 className="section-title">Teams ({teams.length})</h2>
      </div>
      {teams.length === 0 ? (
        <p style={{ color: 'var(--text-muted)', marginBottom: 24 }}>No team data available.</p>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Team</th>
              <th>Country</th>
              <th className="numeric">World Rank</th>
              <th>Placement</th>
              <th className="numeric">Prize</th>
            </tr>
          </thead>
          <tbody>
            {teams.map(t => (
              <tr key={t.id || t.team_id}>
                <td><Link to={`/teams/${t.id || t.team_id}`}>{t.name || t.team_name}</Link></td>
                <td>{t.country || '--'}</td>
                <td className="numeric">{t.world_rank ? `#${t.world_rank}` : '--'}</td>
                <td className={placementClass(t.placement)}>{t.placement || '--'}</td>
                <td className="numeric">{t.prize || '--'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <div className="section-header" style={{ marginTop: 32 }}>
        <h2 className="section-title">Matches ({matches.length})</h2>
      </div>
      {matches.length === 0 ? (
        <p style={{ color: 'var(--text-muted)' }}>No match data available.</p>
      ) : (
        matches.map(m => <MatchCard key={m.id} match={m} />)
      )}
    </div>
  )
}
