import { Link } from 'react-router-dom'

function ratingClass(val) {
  if (val == null) return ''
  if (val >= 1.1) return 'rating-high'
  if (val >= 0.95) return 'rating-mid'
  return 'rating-low'
}

function fmt(val, decimals = 2) {
  if (val == null) return '--'
  return Number(val).toFixed(decimals)
}

const columns = [
  { key: 'nickname', label: 'Player', sortable: true },
  { key: 'country', label: 'Country', sortable: true },
  { key: 'rating_2_0', label: 'Rating', sortable: true, numeric: true },
  { key: 'kd_ratio', label: 'K/D', sortable: true, numeric: true },
  { key: 'adr', label: 'ADR', sortable: true, numeric: true },
  { key: 'kast', label: 'KAST%', sortable: true, numeric: true },
  { key: 'impact', label: 'Impact', sortable: true, numeric: true },
  { key: 'kpr', label: 'KPR', sortable: true, numeric: true },
  { key: 'headshot_percentage', label: 'HS%', sortable: true, numeric: true },
  { key: 'total_maps', label: 'Maps', sortable: true, numeric: true },
]

export default function PlayerTable({ players, sortBy, order, onSort }) {
  function handleSort(key) {
    if (!onSort) return
    if (sortBy === key) {
      onSort(key, order === 'desc' ? 'asc' : 'desc')
    } else {
      onSort(key, 'desc')
    }
  }

  return (
    <table className="data-table">
      <thead>
        <tr>
          <th style={{ width: 40 }}>#</th>
          {columns.map(col => (
            <th
              key={col.key}
              className={[
                col.sortable ? 'sortable' : '',
                sortBy === col.key ? 'sorted' : '',
                col.numeric ? 'numeric' : '',
              ].filter(Boolean).join(' ')}
              onClick={() => col.sortable && handleSort(col.key)}
            >
              {col.label}
              {sortBy === col.key && (
                <span className="sort-arrow">{order === 'desc' ? '\u25BC' : '\u25B2'}</span>
              )}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {players.map((p, i) => (
          <tr key={p.id}>
            <td className="numeric" style={{ color: 'var(--text-muted)' }}>{i + 1}</td>
            <td>
              <Link to={`/players/${p.id}`}>{p.nickname || '--'}</Link>
            </td>
            <td>{p.country || '--'}</td>
            <td className={`numeric ${ratingClass(p.rating_2_0)}`}>{fmt(p.rating_2_0)}</td>
            <td className="numeric">{fmt(p.kd_ratio)}</td>
            <td className="numeric">{fmt(p.adr, 1)}</td>
            <td className="numeric">{p.kast != null ? fmt(p.kast, 1) + '%' : '--'}</td>
            <td className="numeric">{fmt(p.impact)}</td>
            <td className="numeric">{fmt(p.kpr)}</td>
            <td className="numeric">{p.headshot_percentage != null ? fmt(p.headshot_percentage, 1) + '%' : '--'}</td>
            <td className="numeric">{p.total_maps ?? '--'}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
