import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { fetchCartola } from '../../api'
import { useAuth } from '../../components/cartola/AuthProvider'
import PriceChart from '../../components/cartola/PriceChart'

function fmt(val, dec = 2) {
  return val != null ? Number(val).toFixed(dec) : '--'
}

export default function PlayerMarket() {
  const { id } = useParams()
  const [player, setPlayer] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [buying, setBuying] = useState(false)
  const [msg, setMsg] = useState(null)
  const { user } = useAuth()

  useEffect(() => {
    setLoading(true)
    fetchCartola(`/market/${id}`)
      .then(data => setPlayer(data))
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [id])

  async function handleBuy() {
    setBuying(true)
    setMsg(null)
    try {
      const res = await fetchCartola(`/portfolio/buy/${id}`, { method: 'POST' })
      setMsg({ type: 'success', text: `Compra realizada! Saldo: ${res.balance.toFixed(2)}` })
    } catch (err) {
      setMsg({ type: 'error', text: err.message })
    } finally {
      setBuying(false)
    }
  }

  if (loading) return <div className="loading"><span className="loading-spinner"></span>Carregando...</div>
  if (error) return <div className="error-message">{error}</div>
  if (!player) return <div className="empty-state"><p>Jogador nao encontrado.</p></div>

  const change = player.price_change_pct || 0
  const changeClass = change > 0 ? 'rating-high' : change < 0 ? 'rating-low' : 'rating-mid'

  return (
    <div>
      <div style={{ marginBottom: 8 }}>
        <Link to="/cartola/market" style={{ color: 'var(--text-secondary)' }}>Mercado</Link> / {player.nickname}
      </div>

      <div className="team-header">
        <h1>{player.nickname}</h1>
        <div className="team-meta">
          <span>{player.real_name || ''}</span>
          <span>{player.country || ''}</span>
          {player.team && <span>{player.team.name} (#{player.team.world_rank || '?'})</span>}
          {player.age && <span>{player.age} anos</span>}
        </div>
      </div>

      <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', marginBottom: 24 }}>
        <div className="match-card" style={{ flex: 1, minWidth: 200 }}>
          <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>Preco Atual</div>
          <div style={{ fontSize: '2rem', fontWeight: 700 }}>{fmt(player.current_price)}</div>
          <div className={changeClass} style={{ fontSize: '1.1rem' }}>
            {change > 0 ? '+' : ''}{fmt(change)}%
          </div>
        </div>
        <div className="match-card" style={{ flex: 1, minWidth: 200 }}>
          <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>Stats</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginTop: 8 }}>
            <div>Rating: <strong>{fmt(player.rating_2_0)}</strong></div>
            <div>K/D: <strong>{fmt(player.kd_ratio)}</strong></div>
            <div>ADR: <strong>{fmt(player.adr, 1)}</strong></div>
            <div>KAST: <strong>{fmt(player.kast, 1)}%</strong></div>
            <div>Impact: <strong>{fmt(player.impact)}</strong></div>
          </div>
        </div>
      </div>

      {player.roles?.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          {player.roles.map(r => (
            <span key={r.role} className="map-badge" style={{ marginRight: 8 }}>
              {r.role.toUpperCase()}{r.is_primary ? ' (principal)' : ''}
            </span>
          ))}
        </div>
      )}

      {user && (
        <div style={{ marginBottom: 24 }}>
          <button
            onClick={handleBuy}
            disabled={buying}
            style={{
              padding: '10px 24px', background: 'var(--accent-primary)', border: 'none',
              borderRadius: 4, color: '#fff', fontWeight: 600, cursor: 'pointer', fontSize: '1rem',
            }}
          >
            {buying ? 'Comprando...' : `Comprar por ${fmt(player.current_price)}`}
          </button>
          {msg && (
            <div className={msg.type === 'error' ? 'error-message' : ''} style={{ marginTop: 8, color: msg.type === 'success' ? 'var(--accent-primary)' : undefined }}>
              {msg.text}
            </div>
          )}
        </div>
      )}

      <div className="section-header">
        <h2 className="section-title">Historico de Preco (30 dias)</h2>
      </div>
      <PriceChart playerId={id} />
    </div>
  )
}
