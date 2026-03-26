import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchCartola } from '../../api'
import { useAuth } from '../../components/cartola/AuthProvider'

export default function TransactionHistory() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [transactions, setTransactions] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!user) { navigate('/cartola/login'); return }
    // Use ranking endpoint as proxy - TODO: add /transactions endpoint
    setLoading(false)
  }, [user])

  if (loading) return <div className="loading"><span className="loading-spinner"></span>Carregando...</div>

  return (
    <div>
      <div className="page-header">
        <h1>Historico de Transacoes</h1>
      </div>
      <div style={{ color: 'var(--text-muted)' }}>
        Em breve — historico de compras e vendas.
      </div>
    </div>
  )
}
