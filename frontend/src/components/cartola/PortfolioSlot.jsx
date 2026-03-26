import { Link } from 'react-router-dom'

export default function PortfolioSlot({ item, onSell }) {
  if (!item) {
    return (
      <div className="match-card" style={{ opacity: 0.4, textAlign: 'center', padding: 24 }}>
        <div style={{ fontSize: '2rem' }}>+</div>
        <div style={{ color: 'var(--text-muted)' }}>Slot vazio</div>
      </div>
    )
  }

  const profit = (item.current_price - item.buy_price)
  const profitPct = item.buy_price > 0 ? (profit / item.buy_price * 100) : 0
  const profitClass = profit > 0 ? 'rating-high' : profit < 0 ? 'rating-low' : 'rating-mid'

  return (
    <div className="match-card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <Link to={`/cartola/market/${item.player_id}`} style={{ fontWeight: 600, fontSize: '1.1rem' }}>
            {item.nickname || 'Unknown'}
          </Link>
          <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
            {item.team?.name || 'Free agent'}
          </div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontWeight: 700 }}>{item.current_price?.toFixed(2)}</div>
          <div className={profitClass} style={{ fontSize: '0.9rem' }}>
            {profit > 0 ? '+' : ''}{profit.toFixed(2)} ({profitPct > 0 ? '+' : ''}{profitPct.toFixed(1)}%)
          </div>
        </div>
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 8 }}>
        <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>
          Compra: {item.buy_price?.toFixed(2)}
        </span>
        <button
          onClick={() => onSell(item.player_id)}
          style={{
            padding: '4px 12px', background: 'var(--bg-tertiary)', border: '1px solid var(--border)',
            borderRadius: 4, color: 'var(--text-primary)', cursor: 'pointer', fontSize: '0.85rem',
          }}
        >
          Vender
        </button>
      </div>
    </div>
  )
}
