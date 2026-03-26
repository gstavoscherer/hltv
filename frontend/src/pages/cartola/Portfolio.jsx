import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchCartola } from '../../api'
import { useAuth } from '../../components/cartola/AuthProvider'
import PortfolioSlot from '../../components/cartola/PortfolioSlot'

export default function Portfolio() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [portfolio, setPortfolio] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [msg, setMsg] = useState(null)

  useEffect(() => {
    if (!user) {
      navigate('/cartola/login')
      return
    }
    loadPortfolio()
  }, [user])

  function loadPortfolio() {
    setLoading(true)
    fetchCartola('/portfolio')
      .then(data => setPortfolio(data))
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }

  async function handleSell(playerId) {
    setMsg(null)
    try {
      const res = await fetchCartola(`/portfolio/sell/${playerId}`, { method: 'POST' })
      setMsg({ type: 'success', text: `Vendido! Lucro: ${res.profit > 0 ? '+' : ''}${res.profit.toFixed(2)}. Saldo: ${res.balance.toFixed(2)}` })
      loadPortfolio()
    } catch (err) {
      setMsg({ type: 'error', text: err.message })
    }
  }

  if (loading) return <div className="loading"><span className="loading-spinner"></span>Carregando portfolio...</div>
  if (error) return <div className="error-message">{error}</div>
  if (!portfolio) return null

  const slots = [...(portfolio.players || [])]
  while (slots.length < 5) slots.push(null)

  const profitClass = portfolio.profit > 0 ? 'rating-high' : portfolio.profit < 0 ? 'rating-low' : ''

  return (
    <div>
      <div className="page-header">
        <h1>Meu Portfolio</h1>
      </div>

      <div style={{ display: 'flex', gap: 16, marginBottom: 24, flexWrap: 'wrap' }}>
        <div className="match-card" style={{ flex: 1, minWidth: 150, textAlign: 'center' }}>
          <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>Saldo</div>
          <div style={{ fontSize: '1.5rem', fontWeight: 700 }}>{portfolio.balance?.toFixed(2)}</div>
        </div>
        <div className="match-card" style={{ flex: 1, minWidth: 150, textAlign: 'center' }}>
          <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>Patrimonio</div>
          <div style={{ fontSize: '1.5rem', fontWeight: 700 }}>{portfolio.total_value?.toFixed(2)}</div>
        </div>
        <div className="match-card" style={{ flex: 1, minWidth: 150, textAlign: 'center' }}>
          <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>Lucro</div>
          <div className={profitClass} style={{ fontSize: '1.5rem', fontWeight: 700 }}>
            {portfolio.profit > 0 ? '+' : ''}{portfolio.profit?.toFixed(2)}
          </div>
        </div>
      </div>

      {msg && (
        <div className={msg.type === 'error' ? 'error-message' : ''} style={{ marginBottom: 16, color: msg.type === 'success' ? 'var(--accent-primary)' : undefined }}>
          {msg.text}
        </div>
      )}

      <div className="section-header">
        <h2 className="section-title">Meu Time ({portfolio.players?.length || 0}/5)</h2>
      </div>
      {slots.map((item, i) => (
        <PortfolioSlot key={item?.player_id || `empty-${i}`} item={item} onSell={handleSell} />
      ))}
    </div>
  )
}
