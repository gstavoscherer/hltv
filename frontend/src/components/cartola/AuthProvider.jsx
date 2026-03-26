import { createContext, useContext, useState, useEffect } from 'react'
import { getToken, setToken, removeToken } from '../../api'

const AuthContext = createContext(null)

export function useAuth() {
  return useContext(AuthContext)
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)

  useEffect(() => {
    const token = getToken()
    if (token) {
      try {
        const payload = JSON.parse(atob(token.split('.')[1]))
        if (payload.exp * 1000 > Date.now()) {
          setUser({ id: payload.sub, username: payload.username })
        } else {
          removeToken()
        }
      } catch {
        removeToken()
      }
    }
  }, [])

  function login(token, username) {
    setToken(token)
    const payload = JSON.parse(atob(token.split('.')[1]))
    setUser({ id: payload.sub, username })
  }

  function logout() {
    removeToken()
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}
