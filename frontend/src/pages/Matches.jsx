import { useState, useEffect } from 'react'
import { fetchApi } from '../api'
import MatchCard from '../components/MatchCard'

export default function Matches() {
  const [matches, setMatches] = useState([])
  const [events, setEvents] = useState([])
  const [selectedEvent, setSelectedEvent] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetchApi('/events')
      .then(data => setEvents(Array.isArray(data) ? data : []))
      .catch(() => {})
  }, [])

  useEffect(() => {
    setLoading(true)
    const params = selectedEvent ? `?event_id=${selectedEvent}&limit=200` : '?limit=200'
    fetchApi(`/matches${params}`)
      .then(data => setMatches(data.matches || (Array.isArray(data) ? data : [])))
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [selectedEvent])

  return (
    <div>
      <div className="page-header">
        <h1>Matches</h1>
        <p>{matches.length} matches</p>
      </div>

      <div className="search-bar">
        <select
          className="filter-select"
          value={selectedEvent}
          onChange={e => setSelectedEvent(e.target.value)}
        >
          <option value="">All Events</option>
          {events.map(ev => (
            <option key={ev.id} value={ev.id}>{ev.name}</option>
          ))}
        </select>
      </div>

      {error && <div className="error-message">Failed to load matches: {error}</div>}

      {loading ? (
        <div className="loading"><span className="loading-spinner"></span>Loading matches...</div>
      ) : matches.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">&#9876;</div>
          <p>No matches found.</p>
        </div>
      ) : (
        matches.map(m => <MatchCard key={m.id} match={m} />)
      )}
    </div>
  )
}
