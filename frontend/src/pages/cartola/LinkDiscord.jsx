import { useState, useEffect } from 'react'
import { useSearchParams, useNavigate, Link } from 'react-router-dom'
import { fetchCartola } from '../../api'
import { useAuth } from '../../components/cartola/AuthProvider'

export default function LinkDiscord() {
  const [searchParams] = useSearchParams()
  const discordId = searchParams.get('discord_id')
  const { user } = useAuth()
  const navigate = useNavigate()
  const [status, setStatus] = useState('idle')
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!discordId) {
      setError('discord_id nao fornecido na URL')
      return
    }
    if (!user) return

    setStatus('linking')
    fetchCartola('/auth/link-discord', {
      method: 'POST',
      body: JSON.stringify({ discord_id: discordId }),
    })
      .then(() => setStatus('success'))
      .catch(err => {
        setError(err.message)
        setStatus('error')
      })
  }, [discordId, user])

  if (!discordId) {
    return (
      <div style={{ maxWidth: 400, margin: '40px auto', textAlign: 'center' }}>
        <h1>Vincular Discord</h1>
        <p style={{ color: 'var(--text-secondary)' }}>Link invalido. Use o comando /cartola-link no Discord.</p>
      </div>
    )
  }

  if (!user) {
    return (
      <div style={{ maxWidth: 400, margin: '40px auto', textAlign: 'center' }}>
        <h1>Vincular Discord</h1>
        <p style={{ color: 'var(--text-secondary)', marginBottom: 16 }}>
          Faca login ou cadastre-se para vincular seu Discord.
        </p>
        <div style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
          <Link to={`/cartola/login?redirect=/cartola/link?discord_id=${discordId}`}
            style={{ padding: '10px 24px', background: 'var(--accent-primary)', color: '#fff', borderRadius: 4, textDecoration: 'none', fontWeight: 600 }}>
            Login
          </Link>
          <Link to={`/cartola/register?redirect=/cartola/link?discord_id=${discordId}`}
            style={{ padding: '10px 24px', background: 'var(--bg-secondary)', color: 'var(--text-primary)', borderRadius: 4, textDecoration: 'none', fontWeight: 600, border: '1px solid var(--border)' }}>
            Cadastrar
          </Link>
        </div>
      </div>
    )
  }

  if (status === 'linking') {
    return (
      <div style={{ maxWidth: 400, margin: '40px auto', textAlign: 'center' }}>
        <h1>Vinculando...</h1>
      </div>
    )
  }

  if (status === 'success') {
    return (
      <div style={{ maxWidth: 400, margin: '40px auto', textAlign: 'center' }}>
        <h1>Discord Vinculado!</h1>
        <p style={{ color: 'var(--text-secondary)', marginBottom: 16 }}>
          Conta vinculada com sucesso. Agora voce pode usar os comandos do bot no Discord.
        </p>
        <Link to="/cartola/portfolio"
          style={{ padding: '10px 24px', background: 'var(--accent-primary)', color: '#fff', borderRadius: 4, textDecoration: 'none', fontWeight: 600 }}>
          Ver Portfolio
        </Link>
      </div>
    )
  }

  if (error) {
    return (
      <div style={{ maxWidth: 400, margin: '40px auto', textAlign: 'center' }}>
        <h1>Erro</h1>
        <p style={{ color: '#ff4444' }}>{error}</p>
      </div>
    )
  }

  return null
}
