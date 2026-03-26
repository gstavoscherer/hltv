import { Link } from 'react-router-dom'

function formatDate(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

function renderStars(count) {
  if (!count) return null
  return <span className="stars">{'★'.repeat(count)}</span>
}

export default function MatchCard({ match }) {
  const isTeam1Winner = match.winner_name === match.team1_name
  const isTeam2Winner = match.winner_name === match.team2_name

  return (
    <Link to={`/matches/${match.id}`} className="match-card">
      <div className="match-teams">
        <span className={`team-name team-left ${isTeam1Winner ? '' : ''}`}>
          {match.team1_name || 'TBD'}
        </span>
        <div className="match-score">
          <span className={isTeam1Winner ? 'score-winner' : 'score-loser'}>
            {match.score1 ?? 0}
          </span>
          {' - '}
          <span className={isTeam2Winner ? 'score-winner' : 'score-loser'}>
            {match.score2 ?? 0}
          </span>
        </div>
        <span className={`team-name`}>
          {match.team2_name || 'TBD'}
        </span>
      </div>
      <div className="match-meta">
        <div className="match-event">{match.event_name || ''}</div>
        <div className="match-format">
          {match.best_of ? `BO${match.best_of}` : ''}
          {' '}
          {renderStars(match.stars)}
        </div>
        <div>{formatDate(match.date)}</div>
      </div>
    </Link>
  )
}
