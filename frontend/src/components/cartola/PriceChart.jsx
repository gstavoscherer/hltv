import { useState, useEffect } from 'react'
import { fetchCartola } from '../../api'

export default function PriceChart({ playerId }) {
  const [history, setHistory] = useState([])

  useEffect(() => {
    fetchCartola(`/market/${playerId}/history?days=30`)
      .then(data => setHistory(data || []))
      .catch(() => {})
  }, [playerId])

  if (history.length < 2) {
    return <div style={{ color: 'var(--text-muted)', padding: 16 }}>Historico insuficiente para grafico.</div>
  }

  const prices = history.map(h => h.price)
  const minP = Math.min(...prices)
  const maxP = Math.max(...prices)
  const range = maxP - minP || 1

  const width = 600
  const height = 200
  const padding = 30

  const points = history.map((h, i) => {
    const x = padding + (i / (history.length - 1)) * (width - 2 * padding)
    const y = height - padding - ((h.price - minP) / range) * (height - 2 * padding)
    return `${x},${y}`
  }).join(' ')

  const firstDate = new Date(history[0].timestamp).toLocaleDateString('pt-BR')
  const lastDate = new Date(history[history.length - 1].timestamp).toLocaleDateString('pt-BR')

  return (
    <div style={{ background: 'var(--bg-secondary)', borderRadius: 8, padding: 16 }}>
      <svg viewBox={`0 0 ${width} ${height}`} style={{ width: '100%', maxWidth: width }}>
        <polyline
          points={points}
          fill="none"
          stroke="var(--accent-primary)"
          strokeWidth="2"
        />
        <text x={padding} y={height - 5} fill="var(--text-secondary)" fontSize="11">{firstDate}</text>
        <text x={width - padding} y={height - 5} fill="var(--text-secondary)" fontSize="11" textAnchor="end">{lastDate}</text>
        <text x={5} y={padding} fill="var(--text-secondary)" fontSize="11">{maxP.toFixed(1)}</text>
        <text x={5} y={height - padding} fill="var(--text-secondary)" fontSize="11">{minP.toFixed(1)}</text>
      </svg>
    </div>
  )
}
