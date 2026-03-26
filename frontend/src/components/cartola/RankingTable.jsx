import { useState, useEffect } from 'react'
import { fetchCartola } from '../../api'

export default function RankingTable() {
  const [tab, setTab] = useState('patrimonio')
  const [ranking, setRanking] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    const path = tab === 'patrimonio' ? '/ranking' : tab === 'lucro' ? '/ranking/profit' : '/ranking/weekly'
    fetchCartola(path)
      .then(data => setRanking(Array.isArray(data) ? data : []))
      .catch(() => setRanking([]))
      .finally(() => setLoading(false))
  }, [tab])

  const valueField = tab === 'patrimonio' ? 'total_value' : tab === 'lucro' ? 'profit' : 'weekly_profit'
  const valueLabel = tab === 'patrimonio' ? 'Patrimonio' : tab === 'lucro' ? 'Lucro' : 'Lucro Semanal'

  return (
    <div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        {['patrimonio', 'lucro', 'semanal'].map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              padding: '6px 16px', borderRadius: 4, cursor: 'pointer',
              background: tab === t ? 'var(--accent-primary)' : 'var(--bg-tertiary)',
              color: tab === t ? '#fff' : 'var(--text-primary)',
              border: 'none', fontWeight: tab === t ? 600 : 400,
            }}
          >
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="loading"><span className="loading-spinner"></span>Carregando...</div>
      ) : ranking.length === 0 ? (
        <div style={{ color: 'var(--text-muted)' }}>Nenhum jogador no ranking ainda.</div>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Usuario</th>
              <th className="numeric">{valueLabel}</th>
            </tr>
          </thead>
          <tbody>
            {ranking.map((r, i) => (
              <tr key={r.user_id}>
                <td>{i + 1}</td>
                <td>{r.username}</td>
                <td className={`numeric ${r[valueField] > 0 ? 'rating-high' : r[valueField] < 0 ? 'rating-low' : ''}`}>
                  {r[valueField]?.toFixed(2)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
