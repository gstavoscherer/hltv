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

export default function MapStatsTable({ stats, teamName }) {
  if (!stats || stats.length === 0) {
    return <p style={{ color: 'var(--text-muted)', padding: '12px 0' }}>No player stats available.</p>
  }

  return (
    <div style={{ marginBottom: 24 }}>
      {teamName && <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 8, color: 'var(--text-secondary)' }}>{teamName}</h3>}
      <table className="data-table">
        <thead>
          <tr>
            <th>Player</th>
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
          {stats.map((s, i) => (
            <tr key={i}>
              <td>
                {s.player?.nickname || s.player_name || s.nickname || `Player ${s.player_id}`}
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
    </div>
  )
}
