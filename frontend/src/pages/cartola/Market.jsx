import { useState, useEffect } from 'react'
import { fetchCartola } from '../../api'
import PlayerMarketCard from '../../components/cartola/PlayerMarketCard'

const ROLES = ['', 'awp', 'rifler', 'igl', 'lurker', 'entry', 'support']
const SORT_OPTIONS = [
  { value: 'current_price', label: 'Preco' },
  { value: 'price_change_pct', label: 'Variacao' },
  { value: 'rating', label: 'Rating' },
]

export default function Market() {
  const [players, setPlayers] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [role, setRole] = useState('')
  const [sortBy, setSortBy] = useState('current_price')
  const [order, setOrder] = useState('desc')
  const [offset, setOffset] = useState(0)
  const limit = 30

  useEffect(() => {
    setLoading(true)
    let params = `?sort_by=${sortBy}&order=${order}&limit=${limit}&offset=${offset}`
    if (role) params += `&role=${role}`
    fetchCartola(`/market${params}`)
      .then(data => {
        setPlayers(data.players || [])
        setTotal(data.total || 0)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [role, sortBy, order, offset])

  return (
    <div>
      <div className="page-header">
        <h1>Mercado CartolaCS</h1>
        <p>{total} jogadores</p>
      </div>

      <div className="search-bar" style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        <select className="filter-select" value={role} onChange={e => { setRole(e.target.value); setOffset(0) }}>
          <option value="">Todas posicoes</option>
          {ROLES.filter(Boolean).map(r => <option key={r} value={r}>{r.toUpperCase()}</option>)}
        </select>
        <select className="filter-select" value={sortBy} onChange={e => setSortBy(e.target.value)}>
          {SORT_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
        <button
          className="filter-select"
          onClick={() => setOrder(o => o === 'desc' ? 'asc' : 'desc')}
          style={{ cursor: 'pointer' }}
        >
          {order === 'desc' ? 'Maior primeiro' : 'Menor primeiro'}
        </button>
      </div>

      {loading ? (
        <div className="loading"><span className="loading-spinner"></span>Carregando mercado...</div>
      ) : players.length === 0 ? (
        <div className="empty-state"><p>Nenhum jogador no mercado.</p></div>
      ) : (
        <>
          {players.map(p => <PlayerMarketCard key={p.id} player={p} />)}
          <div style={{ display: 'flex', justifyContent: 'center', gap: 12, marginTop: 24 }}>
            {offset > 0 && (
              <button className="filter-select" style={{ cursor: 'pointer' }} onClick={() => setOffset(o => Math.max(0, o - limit))}>
                Anterior
              </button>
            )}
            {offset + limit < total && (
              <button className="filter-select" style={{ cursor: 'pointer' }} onClick={() => setOffset(o => o + limit)}>
                Proximo
              </button>
            )}
          </div>
        </>
      )}
    </div>
  )
}
