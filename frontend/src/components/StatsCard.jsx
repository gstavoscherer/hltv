export default function StatsCard({ value, label, accent }) {
  const cls = accent ? `stat-card accent-${accent}` : 'stat-card'
  return (
    <div className={cls}>
      <div className="stat-value">{value ?? '--'}</div>
      <div className="stat-label">{label}</div>
    </div>
  )
}
