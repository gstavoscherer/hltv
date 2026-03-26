import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { fetchApi } from '../api'

export default function Teams() {
  const [teams, setTeams] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetchApi('/teams')
      .then(data => {
        const arr = Array.isArray(data) ? data : []
        arr.sort((a, b) => {
          if (a.world_rank && b.world_rank) return a.world_rank - b.world_rank
          if (a.world_rank) return -1
          if (b.world_rank) return 1
          return (a.name || '').localeCompare(b.name || '')
        })
        setTeams(arr)
      })
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="loading"><span className="loading-spinner"></span>Loading teams...</div>
  if (error) return <div className="error-message">Failed to load teams: {error}</div>

  return (
    <div>
      <div className="page-header">
        <h1>Teams</h1>
        <p>{teams.length} teams in database</p>
      </div>

      {teams.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">&#9872;</div>
          <p>No teams found.</p>
        </div>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th className="numeric">Rank</th>
              <th>Team</th>
              <th>Country</th>
            </tr>
          </thead>
          <tbody>
            {teams.map(t => (
              <tr key={t.id}>
                <td className="numeric">{t.world_rank ? `#${t.world_rank}` : '--'}</td>
                <td><Link to={`/teams/${t.id}`}>{t.name}</Link></td>
                <td>{t.country || '--'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
