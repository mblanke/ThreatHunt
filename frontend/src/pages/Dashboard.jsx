import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, FolderOpen, Calendar, User } from 'lucide-react'

const Dashboard = ({ user }) => {
  const [hunts, setHunts] = useState([])
  const [loading, setLoading] = useState(true)
  const [showNewHunt, setShowNewHunt] = useState(false)
  const [newHunt, setNewHunt] = useState({ name: '', description: '' })
  const navigate = useNavigate()

  useEffect(() => {
    fetchHunts()
  }, [])

  const fetchHunts = async () => {
    try {
      const token = localStorage.getItem('token')
      const response = await fetch('/api/hunts', {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      
      if (response.ok) {
        const data = await response.json()
        setHunts(data.hunts)
      }
    } catch (err) {
      console.error('Failed to fetch hunts:', err)
    }
    setLoading(false)
  }

  const createHunt = async (e) => {
    e.preventDefault()
    try {
      const token = localStorage.getItem('token')
      const response = await fetch('/api/hunts', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(newHunt)
      })

      if (response.ok) {
        const data = await response.json()
        navigate(`/hunt/${data.hunt.id}`)
      }
    } catch (err) {
      console.error('Failed to create hunt:', err)
    }
  }

  if (loading) {
    return <div className="flex items-center justify-center h-64">Loading...</div>
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Welcome back, {user.username}</h1>
          <p className="text-zinc-400">Choose a hunt to continue or start a new investigation</p>
        </div>
        <button
          onClick={() => setShowNewHunt(true)}
          className="bg-cyan-600 hover:bg-cyan-700 text-white px-4 py-2 rounded-lg flex items-center"
        >
          <Plus className="w-4 h-4 mr-2" />
          New Hunt
        </button>
      </div>

      {showNewHunt && (
        <div className="bg-zinc-800 p-6 rounded-lg">
          <h2 className="text-xl font-bold mb-4">Create New Hunt</h2>
          <form onSubmit={createHunt} className="space-y-4">
            <input
              type="text"
              placeholder="Hunt Name"
              value={newHunt.name}
              onChange={(e) => setNewHunt({...newHunt, name: e.target.value})}
              className="w-full p-3 bg-zinc-700 rounded-lg border border-zinc-600 focus:border-cyan-400 outline-none"
              required
            />
            <textarea
              placeholder="Description"
              value={newHunt.description}
              onChange={(e) => setNewHunt({...newHunt, description: e.target.value})}
              className="w-full p-3 bg-zinc-700 rounded-lg border border-zinc-600 focus:border-cyan-400 outline-none h-24"
            />
            <div className="flex space-x-2">
              <button type="submit" className="bg-cyan-600 hover:bg-cyan-700 text-white px-4 py-2 rounded-lg">
                Create Hunt
              </button>
              <button
                type="button"
                onClick={() => setShowNewHunt(false)}
                className="bg-zinc-600 hover:bg-zinc-700 text-white px-4 py-2 rounded-lg"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {hunts.map(hunt => (
          <div
            key={hunt.id}
            onClick={() => navigate(`/hunt/${hunt.id}`)}
            className="bg-zinc-800 p-6 rounded-lg cursor-pointer hover:bg-zinc-750 transition-colors"
          >
            <div className="flex items-center mb-4">
              <FolderOpen className="w-8 h-8 text-cyan-400 mr-3" />
              <div>
                <h3 className="font-semibold">{hunt.name}</h3>
                <p className="text-sm text-zinc-400">{hunt.status}</p>
              </div>
            </div>
            <p className="text-zinc-400 text-sm mb-3">{hunt.description}</p>
            <div className="flex items-center text-xs text-zinc-500">
              <Calendar className="w-3 h-3 mr-1" />
              {new Date(hunt.created_at).toLocaleDateString()}
            </div>
          </div>
        ))}
      </div>

      {hunts.length === 0 && (
        <div className="text-center py-12">
          <FolderOpen className="w-16 h-16 text-zinc-600 mx-auto mb-4" />
          <h3 className="text-xl font-semibold mb-2">No hunts yet</h3>
          <p className="text-zinc-400 mb-4">Start your first threat hunting investigation</p>
          <button
            onClick={() => setShowNewHunt(true)}
            className="bg-cyan-600 hover:bg-cyan-700 text-white px-6 py-3 rounded-lg"
          >
            Create Your First Hunt
          </button>
        </div>
      )}
    </div>
  )
}

export default Dashboard
