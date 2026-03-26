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

  const team1Name = match.team1?.name || 'TBD'
  const team2Name = match.team2?.name || 'TBD'
  const team1Id = match.team1?.id
  const team2Id = match.team2?.id
  const winnerName = match.winner?.name
  const eventName = match.event?.name
  const eventId = match.event?.id

  const isTeam1Winner = winnerName === team1Name
  const isTeam2Winner = winnerName === team2Name

  return (
    <div>
      <div className="page-header">
        <p style={{ marginBottom: 8 }}>
          {eventName && (
            <Link to={`/events/${eventId}`}>{eventName}</Link>
          )}
          {' '}
          {match.best_of ? `- BO${match.best_of}` : ''}
          {' '}
          {match.stars ? <span className="stars">{'★'.repeat(match.stars)}</span> : ''}
        </p>
        <h1 style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
          <Link to={`/teams/${team1Id}`} style={{ color: 'inherit', textDecoration: 'none' }}>{team1Name}</Link>
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
          <Link to={`/teams/${team2Id}`} style={{ color: 'inherit', textDecoration: 'none' }}>{team2Name}</Link>
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
                {m.team1_score != null && m.team2_score != null && (
                  <span style={{ marginLeft: 6 }}>({m.team1_score}-{m.team2_score})</span>
                )}
              </button>
            ))}
          </div>

          {currentMap && (
            <div>
              <div className="map-score-header">
                <span>{team1Name}</span>
                <span className="map-team-score" style={{
                  color: (currentMap.team1_score ?? 0) > (currentMap.team2_score ?? 0)
                    ? 'var(--accent-green)' : 'var(--text-muted)'
                }}>
                  {currentMap.team1_score ?? 0}
                </span>
                <span style={{ color: 'var(--text-muted)' }}>-</span>
                <span className="map-team-score" style={{
                  color: (currentMap.team2_score ?? 0) > (currentMap.team1_score ?? 0)
                    ? 'var(--accent-green)' : 'var(--text-muted)'
                }}>
                  {currentMap.team2_score ?? 0}
                </span>
                <span>{team2Name}</span>
              </div>

              {currentMap.player_stats && currentMap.player_stats.length > 0 ? (
                <>
                  <MapStatsTable
                    stats={currentMap.player_stats.filter(s => {
                      const tid = s.team?.id || s.team_id
                      return tid === team1Id
                    })}
                    teamName={team1Name}
                  />
                  <MapStatsTable
                    stats={currentMap.player_stats.filter(s => {
                      const tid = s.team?.id || s.team_id
                      return tid === team2Id
                    })}
                    teamName={team2Name}
                  />
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
