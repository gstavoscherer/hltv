import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { fetchApi } from '../api'
import MatchCard from '../components/MatchCard'

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

export default function TeamDetail() {
  const { id } = useParams()
  const [team, setTeam] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    setLoading(true)
    fetchApi(`/teams/${id}`)
      .then(data => setTeam(data))
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) return <div className="loading"><span className="loading-spinner"></span>Loading team...</div>
  if (error) return <div className="error-message">Failed to load team: {error}</div>
  if (!team) return <div className="empty-state"><p>Team not found.</p></div>

  const roster = team.roster || []
  const matches = team.recent_matches || []

  return (
    <div>
      <div className="team-header">
        <h1>{team.name}</h1>
        <div className="team-meta">
          <span>{team.country || 'Unknown country'}</span>
          {team.world_rank && <span>World Rank #{team.world_rank}</span>}
        </div>
      </div>

      <div className="section-header">
        <h2 className="section-title">Roster ({roster.length})</h2>
      </div>
      {roster.length === 0 ? (
        <p style={{ color: 'var(--text-muted)', marginBottom: 24 }}>No roster data available.</p>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Player</th>
              <th>Real Name</th>
              <th>Country</th>
              <th>Role</th>
              <th className="numeric">Rating</th>
              <th className="numeric">K/D</th>
              <th className="numeric">ADR</th>
            </tr>
          </thead>
          <tbody>
            {roster.map(r => {
              const p = r.player || r
              return (
                <tr key={p.id || r.player_id}>
                  <td><Link to={`/players/${p.id}`}>{p.nickname || '--'}</Link></td>
                  <td style={{ color: 'var(--text-secondary)' }}>{p.real_name || '--'}</td>
                  <td>{p.country || '--'}</td>
                  <td>{r.role || '--'}</td>
                  <td className={`numeric ${ratingClass(p.rating_2_0)}`}>{fmt(p.rating_2_0)}</td>
                  <td className="numeric">{fmt(p.kd_ratio)}</td>
                  <td className="numeric">{fmt(p.adr, 1)}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}

      <div className="section-header" style={{ marginTop: 32 }}>
        <h2 className="section-title">Recent Matches ({matches.length})</h2>
      </div>
      {matches.length === 0 ? (
        <p style={{ color: 'var(--text-muted)' }}>No match data available.</p>
      ) : (
        matches.map(m => <MatchCard key={m.id} match={m} />)
      )}
    </div>
  )
}
