import { Link } from 'react-router-dom'

export default function PlayerMarketCard({ player }) {
  const change = player.price_change_pct || 0
  const changeClass = change > 0 ? 'rating-high' : change < 0 ? 'rating-low' : 'rating-mid'

  return (
    <Link to={`/cartola/market/${player.id}`} className="match-card" style={{ textDecoration: 'none' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div style={{ fontWeight: 600, fontSize: '1.1rem' }}>{player.nickname}</div>
          <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
            {player.team?.name || 'Free agent'}
            {player.roles?.length > 0 && (
              <span style={{ marginLeft: 8 }}>
                {player.roles.map(r => (
                  <span key={r.role} className="map-badge" style={{ marginLeft: 4 }}>{r.role.toUpperCase()}</span>
                ))}
              </span>
            )}
          </div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontWeight: 700, fontSize: '1.2rem' }}>{player.current_price?.toFixed(2)}</div>
          <div className={changeClass} style={{ fontSize: '0.9rem' }}>
            {change > 0 ? '+' : ''}{change.toFixed(2)}%
          </div>
        </div>
      </div>
      <div style={{ display: 'flex', gap: 16, marginTop: 8, color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
        <span>Rating: {player.rating_2_0?.toFixed(2) || '--'}</span>
        <span>{player.country || ''}</span>
      </div>
    </Link>
  )
}
