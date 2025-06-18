import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Shield, User, Lock } from 'lucide-react'

const LoginPage = ({ onLogin }) => {
  const [credentials, setCredentials] = useState({ username: '', password: '' })
  const [isLogin, setIsLogin] = useState(true)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')

    try {
      const endpoint = isLogin ? '/api/auth/login' : '/api/auth/register'
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(credentials)
      })

      const data = await response.json()

      if (response.ok) {
        localStorage.setItem('token', data.access_token)
        onLogin(data.user)
        navigate('/dashboard')
      } else {
        setError(data.error)
      }
    } catch (err) {
      setError('Connection failed')
    }
    setLoading(false)
  }

  return (
    <div className="min-h-screen bg-zinc-900 flex items-center justify-center">
      <div className="bg-zinc-800 p-8 rounded-lg shadow-lg w-96">
        <div className="text-center mb-6">
          <Shield className="w-16 h-16 text-cyan-400 mx-auto mb-4" />
          <h1 className="text-2xl font-bold">Cyber Threat Hunter</h1>
          <p className="text-zinc-400">Advanced threat hunting platform</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-2">Username</label>
            <div className="relative">
              <User className="w-5 h-5 absolute left-3 top-3 text-zinc-400" />
              <input
                type="text"
                value={credentials.username}
                onChange={(e) => setCredentials({...credentials, username: e.target.value})}
                className="w-full pl-10 p-3 bg-zinc-700 rounded-lg border border-zinc-600 focus:border-cyan-400 outline-none"
                required
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">Password</label>
            <div className="relative">
              <Lock className="w-5 h-5 absolute left-3 top-3 text-zinc-400" />
              <input
                type="password"
                value={credentials.password}
                onChange={(e) => setCredentials({...credentials, password: e.target.value})}
                className="w-full pl-10 p-3 bg-zinc-700 rounded-lg border border-zinc-600 focus:border-cyan-400 outline-none"
                required
              />
            </div>
          </div>

          {error && (
            <div className="text-red-400 text-sm">{error}</div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-cyan-600 hover:bg-cyan-700 text-white p-3 rounded-lg disabled:opacity-50"
          >
            {loading ? 'Please wait...' : (isLogin ? 'Login' : 'Register')}
          </button>
        </form>

        <div className="text-center mt-4">
          <button
            onClick={() => setIsLogin(!isLogin)}
            className="text-cyan-400 hover:text-cyan-300"
          >
            {isLogin ? 'Need an account? Register' : 'Already have an account? Login'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default LoginPage
