export default function VetoList({ vetos }) {
  if (!vetos || vetos.length === 0) {
    return <p style={{ color: 'var(--text-muted)', padding: '12px 0' }}>No veto data available.</p>
  }

  function actionClass(action) {
    if (!action) return 'veto-action'
    const a = action.toLowerCase()
    if (a.includes('ban') || a.includes('remove')) return 'veto-action veto-ban'
    if (a.includes('pick')) return 'veto-action veto-pick'
    if (a.includes('decider') || a.includes('left')) return 'veto-action veto-decider'
    return 'veto-action'
  }

  return (
    <div className="veto-list">
      {vetos.map((v, i) => (
        <div className="veto-item" key={i}>
          <span className="veto-team">{v.team?.name || v.team_name || '--'}</span>
          <span className={actionClass(v.action)}>{v.action || 'VETO'}</span>
          <span className="veto-map">{v.map_name || '--'}</span>
        </div>
      ))}
    </div>
  )
}
