import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import api from '../services/api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser]       = useState(null)
  const [token, setToken]     = useState(() => localStorage.getItem('ja_token'))
  const [loading, setLoading] = useState(true)

  // Attach token to every request when it changes
  useEffect(() => {
    if (token) {
      api.defaults.headers.common['Authorization'] = `Bearer ${token}`
      localStorage.setItem('ja_token', token)
    } else {
      delete api.defaults.headers.common['Authorization']
      localStorage.removeItem('ja_token')
    }
  }, [token])

  // Hydrate current user on mount / token change
  useEffect(() => {
    const hydrate = async () => {
      if (!token) { setLoading(false); return }
      try {
        const { data } = await api.get('/api/auth/me')
        setUser(data)
      } catch {
        setToken(null)
        setUser(null)
      } finally {
        setLoading(false)
      }
    }
    hydrate()
  }, [token])

  const login = useCallback(async (email, password) => {
    const { data } = await api.post('/api/auth/login', { email, password })
    setToken(data.access_token)
    setUser(data.user)
    return data.user
  }, [])

  const signup = useCallback(async (username, email, password) => {
    const { data } = await api.post('/api/auth/signup', { username, email, password })
    setToken(data.access_token)
    setUser(data.user)
    return data.user
  }, [])

  const logout = useCallback(() => {
    setToken(null)
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider value={{ user, token, loading, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be inside AuthProvider')
  return ctx
}
