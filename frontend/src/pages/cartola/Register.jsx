import { useState } from 'react'
import { useNavigate, Link, useSearchParams } from 'react-router-dom'
import { fetchCartola } from '../../api'
import { useAuth } from '../../components/cartola/AuthProvider'

export default function Register() {
  const [username, setUsername] = useState('')
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
      const data = await fetchCartola('/auth/register', {
        method: 'POST',
        body: JSON.stringify({ username, email, password }),
      })
      login(data.token, data.username)
      navigate(redirect || '/cartola/portfolio')
    } catch (err) {
      setError(err.message)
    }
  }

  const inputStyle = { width: '100%', padding: 10, marginBottom: 12, background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: 4, color: 'var(--text-primary)' }

  return (
    <div style={{ maxWidth: 400, margin: '40px auto' }}>
      <h1>Cadastro CartolaCS</h1>
      {error && <div className="error-message">{error}</div>}
      <form onSubmit={handleSubmit}>
        <input type="text" placeholder="Username" value={username} onChange={e => setUsername(e.target.value)} required style={inputStyle} />
        <input type="email" placeholder="Email" value={email} onChange={e => setEmail(e.target.value)} required style={inputStyle} />
        <input type="password" placeholder="Senha (min 6 caracteres)" value={password} onChange={e => setPassword(e.target.value)} required style={inputStyle} />
        <button type="submit" style={{ width: '100%', padding: 12, background: 'var(--accent-primary)', border: 'none', borderRadius: 4, color: '#fff', fontWeight: 600, cursor: 'pointer', marginTop: 4 }}>
          Criar conta
        </button>
      </form>
      <p style={{ marginTop: 16, color: 'var(--text-secondary)', textAlign: 'center' }}>
        Ja tem conta? <Link to={`/cartola/login${redirect ? `?redirect=${encodeURIComponent(redirect)}` : ''}`}>Entrar</Link>
      </p>
    </div>
  )
}
