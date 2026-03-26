import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { fetchApi } from '../api'

function formatDate(dateStr) {
  if (!dateStr) return '--'
  const d = new Date(dateStr)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

export default function Events() {
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetchApi('/events')
      .then(data => setEvents(Array.isArray(data) ? data : []))
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="loading"><span className="loading-spinner"></span>Loading events...</div>
  if (error) return <div className="error-message">Failed to load events: {error}</div>

  return (
    <div>
      <div className="page-header">
        <h1>Events</h1>
        <p>{events.length} events in database</p>
      </div>

      {events.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">&#9734;</div>
          <p>No events found.</p>
        </div>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Event</th>
              <th>Location</th>
              <th className="numeric">Prize Pool</th>
              <th className="numeric">Teams</th>
              <th className="numeric">Matches</th>
              <th>Start Date</th>
              <th>End Date</th>
            </tr>
          </thead>
          <tbody>
            {events.map(e => (
              <tr key={e.id}>
                <td><Link to={`/events/${e.id}`}>{e.name}</Link></td>
                <td>{e.location || '--'}</td>
                <td className="numeric">{e.prize_pool || '--'}</td>
                <td className="numeric">{e.team_count ?? '--'}</td>
                <td className="numeric">{e.match_count ?? '--'}</td>
                <td>{formatDate(e.start_date)}</td>
                <td>{formatDate(e.end_date)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
