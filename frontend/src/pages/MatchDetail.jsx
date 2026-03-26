import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { fetchApi } from '../api'
import VetoList from '../components/VetoList'
import MapStatsTable from '../components/MapStatsTable'

function formatDate(dateStr) {
  if (!dateStr) return '--'
  const d = new Date(dateStr)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export default function MatchDetail() {
  const { id } = useParams()
  const [match, setMatch] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [activeMap, setActiveMap] = useState(0)

  useEffect(() => {
    setLoading(true)
    fetchApi(`/matches/${id}`)
      .then(data => setMatch(data))
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) return <div className="loading"><span className="loading-spinner"></span>Loading match...</div>
  if (error) return <div className="error-message">Failed to load match: {error}</div>
  if (!match) return <div className="empty-state"><p>Match not found.</p></div>

  const maps = match.maps || []
  const vetos = match.vetos || []
  const currentMap = maps[activeMap]

  const isTeam1Winner = match.winner_name === match.team1_name
  const isTeam2Winner = match.winner_name === match.team2_name

  return (
    <div>
      <div className="page-header">
        <p style={{ marginBottom: 8 }}>
          {match.event_name && (
            <Link to={`/events/${match.event_id}`}>{match.event_name}</Link>
          )}
          {' '}
          {match.best_of ? `- BO${match.best_of}` : ''}
          {' '}
          {match.stars ? <span className="stars">{'★'.repeat(match.stars)}</span> : ''}
        </p>
        <h1 style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
          <span>{match.team1_name || 'TBD'}</span>
          <span style={{
            fontSize: 32,
            fontWeight: 700,
            padding: '4px 16px',
            background: 'var(--bg-tertiary)',
            borderRadius: 8,
          }}>
            <span className={isTeam1Winner ? 'score-winner' : 'score-loser'}>{match.score1 ?? 0}</span>
            {' - '}
            <span className={isTeam2Winner ? 'score-winner' : 'score-loser'}>{match.score2 ?? 0}</span>
          </span>
          <span>{match.team2_name || 'TBD'}</span>
        </h1>
        <p>{formatDate(match.date)}</p>
      </div>

      {vetos.length > 0 && (
        <>
          <div className="section-header">
            <h2 className="section-title">Vetos</h2>
          </div>
          <VetoList vetos={vetos} />
        </>
      )}

      {maps.length > 0 && (
        <>
          <div className="section-header" style={{ marginTop: 24 }}>
            <h2 className="section-title">Maps</h2>
          </div>

          <div className="map-tabs">
            {maps.map((m, i) => (
              <button
                key={i}
                className={`map-tab ${activeMap === i ? 'active' : ''}`}
                onClick={() => setActiveMap(i)}
              >
                {m.map_name || `Map ${i + 1}`}
                {m.score_team1 != null && m.score_team2 != null && (
                  <span style={{ marginLeft: 6 }}>({m.score_team1}-{m.score_team2})</span>
                )}
              </button>
            ))}
          </div>

          {currentMap && (
            <div>
              <div className="map-score-header">
                <span>{match.team1_name}</span>
                <span className="map-team-score" style={{
                  color: (currentMap.score_team1 ?? 0) > (currentMap.score_team2 ?? 0)
                    ? 'var(--accent-green)' : 'var(--text-muted)'
                }}>
                  {currentMap.score_team1 ?? 0}
                </span>
                <span style={{ color: 'var(--text-muted)' }}>-</span>
                <span className="map-team-score" style={{
                  color: (currentMap.score_team2 ?? 0) > (currentMap.score_team1 ?? 0)
                    ? 'var(--accent-green)' : 'var(--text-muted)'
                }}>
                  {currentMap.score_team2 ?? 0}
                </span>
                <span>{match.team2_name}</span>
              </div>

              {currentMap.player_stats && currentMap.player_stats.length > 0 ? (
                <>
                  <MapStatsTable
                    stats={currentMap.player_stats.filter(s => s.team_name === match.team1_name || s.team_id === match.team1_id)}
                    teamName={match.team1_name}
                  />
                  <MapStatsTable
                    stats={currentMap.player_stats.filter(s => s.team_name === match.team2_name || s.team_id === match.team2_id)}
                    teamName={match.team2_name}
                  />
                  {/* If we can't split by team, show all */}
                  {currentMap.player_stats.filter(s => s.team_name === match.team1_name || s.team_id === match.team1_id).length === 0 &&
                   currentMap.player_stats.filter(s => s.team_name === match.team2_name || s.team_id === match.team2_id).length === 0 && (
                    <MapStatsTable stats={currentMap.player_stats} />
                  )}
                </>
              ) : (
                <p style={{ color: 'var(--text-muted)' }}>No player stats for this map.</p>
              )}
            </div>
          )}
        </>
      )}

      {maps.length === 0 && (
        <p style={{ color: 'var(--text-muted)', marginTop: 24 }}>No map data available for this match.</p>
      )}
    </div>
  )
}
