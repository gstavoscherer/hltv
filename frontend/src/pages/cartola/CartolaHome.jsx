import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { fetchCartola } from '../../api'
import { useAuth } from '../../components/cartola/AuthProvider'

export default function CartolaHome() {
  const { user } = useAuth()
  const [topPlayers, setTopPlayers] = useState([])
  const [topGainers, setTopGainers] = useState([])
  const [topLosers, setTopLosers] = useState([])
  const [ranking, setRanking] = useState([])

  useEffect(() => {
    fetchCartola('/market?sort_by=current_price&order=desc&limit=5')
      .then(d => setTopPlayers(d.players || []))
      .catch(() => {})
    fetchCartola('/market?sort_by=price_change_pct&order=desc&limit=5')
      .then(d => setTopGainers(d.players || []))
      .catch(() => {})
    fetchCartola('/market?sort_by=price_change_pct&order=asc&limit=5')
      .then(d => setTopLosers(d.players || []))
      .catch(() => {})
    fetchCartola('/ranking?limit=10')
      .then(d => setRanking(Array.isArray(d) ? d : []))
      .catch(() => {})
  }, [])

  return (
    <div>
      <div className="page-header">
        <h1>CartolaCS</h1>
        <p>Fantasy CS2 — Monte seu time, compre e venda jogadores</p>
      </div>

      <div style={{ display: 'flex', gap: 12, marginBottom: 24 }}>
        <Link to="/cartola/market" className="filter-select" style={{ textDecoration: 'none', textAlign: 'center', padding: '10px 20px' }}>
          Mercado
        </Link>
        {user ? (
          <Link to="/cartola/portfolio" className="filter-select" style={{ textDecoration: 'none', textAlign: 'center', padding: '10px 20px' }}>
            Meu Portfolio
          </Link>
        ) : (
          <Link to="/cartola/login" className="filter-select" style={{ textDecoration: 'none', textAlign: 'center', padding: '10px 20px' }}>
            Entrar
          </Link>
        )}
        <Link to="/cartola/ranking" className="filter-select" style={{ textDecoration: 'none', textAlign: 'center', padding: '10px 20px' }}>
          Ranking
        </Link>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 24 }}>
        {/* Top valorizacoes */}
        <div>
          <div className="section-header"><h2 className="section-title">Maiores Altas</h2></div>
          {topGainers.map(p => (
            <Link key={p.id} to={`/cartola/market/${p.id}`} className="match-card" style={{ display: 'flex', justifyContent: 'space-between', textDecoration: 'none', marginBottom: 4 }}>
              <span>{p.nickname}</span>
              <span className="rating-high">+{(p.price_change_pct || 0).toFixed(2)}%</span>
            </Link>
          ))}
        </div>

        {/* Top desvalorizacoes */}
        <div>
          <div className="section-header"><h2 className="section-title">Maiores Baixas</h2></div>
          {topLosers.map(p => (
            <Link key={p.id} to={`/cartola/market/${p.id}`} className="match-card" style={{ display: 'flex', justifyContent: 'space-between', textDecoration: 'none', marginBottom: 4 }}>
              <span>{p.nickname}</span>
              <span className="rating-low">{(p.price_change_pct || 0).toFixed(2)}%</span>
            </Link>
          ))}
        </div>

        {/* Top precos */}
        <div>
          <div className="section-header"><h2 className="section-title">Mais Caros</h2></div>
          {topPlayers.map(p => (
            <Link key={p.id} to={`/cartola/market/${p.id}`} className="match-card" style={{ display: 'flex', justifyContent: 'space-between', textDecoration: 'none', marginBottom: 4 }}>
              <span>{p.nickname}</span>
              <span style={{ fontWeight: 600 }}>{(p.current_price || 0).toFixed(2)}</span>
            </Link>
          ))}
        </div>

        {/* Ranking */}
        <div>
          <div className="section-header"><h2 className="section-title">Ranking Top 10</h2></div>
          {ranking.length === 0 ? (
            <div style={{ color: 'var(--text-muted)' }}>Nenhum jogador ainda.</div>
          ) : ranking.map((r, i) => (
            <div key={r.user_id} className="match-card" style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
              <span>#{i + 1} {r.username}</span>
              <span style={{ fontWeight: 600 }}>{r.total_value?.toFixed(2)}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
