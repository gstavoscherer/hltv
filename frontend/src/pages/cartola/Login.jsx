import { useState } from 'react'
import { useNavigate, Link, useSearchParams } from 'react-router-dom'
import { fetchCartola } from '../../api'
import { useAuth } from '../../components/cartola/AuthProvider'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const { login } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const redirect = searchParams.get('redirect')

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)
    try {
      const data = await fetchCartola('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      })
      login(data.token, data.username)
      navigate(redirect || '/cartola/portfolio')
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div style={{ maxWidth: 400, margin: '40px auto' }}>
      <h1>Login CartolaCS</h1>
      {error && <div className="error-message">{error}</div>}
      <form onSubmit={handleSubmit}>
        <input type="email" placeholder="Email" value={email} onChange={e => setEmail(e.target.value)} required
          style={{ width: '100%', padding: 10, marginBottom: 12, background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: 4, color: 'var(--text-primary)' }} />
        <input type="password" placeholder="Senha" value={password} onChange={e => setPassword(e.target.value)} required
          style={{ width: '100%', padding: 10, marginBottom: 16, background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: 4, color: 'var(--text-primary)' }} />
        <button type="submit" style={{ width: '100%', padding: 12, background: 'var(--accent-primary)', border: 'none', borderRadius: 4, color: '#fff', fontWeight: 600, cursor: 'pointer' }}>
          Entrar
        </button>
      </form>
      <p style={{ marginTop: 16, color: 'var(--text-secondary)', textAlign: 'center' }}>
        Nao tem conta? <Link to={`/cartola/register${redirect ? `?redirect=${encodeURIComponent(redirect)}` : ''}`}>Cadastre-se</Link>
      </p>
    </div>
  )
}
