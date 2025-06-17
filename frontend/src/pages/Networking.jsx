import { Network, Activity, Globe } from 'lucide-react'

const Networking = () => {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold mb-2">Network Analysis</h1>
        <p className="text-zinc-400">Analyze network connections and traffic patterns</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-zinc-800 rounded-lg p-6 shadow-lg">
          <Network className="w-8 h-8 text-cyan-400 mb-4" />
          <h3 className="text-lg font-semibold mb-2">Active Connections</h3>
          <p className="text-2xl font-bold text-cyan-400">0</p>
        </div>
      </div>
    </div>
  )
}

export default Networking
