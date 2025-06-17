import { Package, List, Search } from 'lucide-react'

const Applications = () => {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold mb-2">Application Analysis</h1>
        <p className="text-zinc-400">Monitor and analyze running applications</p>
      </div>

      <div className="bg-zinc-800 rounded-lg p-6 shadow-lg">
        <h2 className="text-xl font-bold mb-4">Application Inventory</h2>
        <p className="text-zinc-400">No applications loaded</p>
      </div>
    </div>
  )
}

export default Applications
