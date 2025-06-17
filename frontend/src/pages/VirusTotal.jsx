import { Shield, Search, FileText } from 'lucide-react'

const VirusTotal = () => {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold mb-2">VirusTotal Integration</h1>
        <p className="text-zinc-400">Check file and URL reputation</p>
      </div>

      <div className="bg-zinc-800 rounded-lg p-6 shadow-lg">
        <h2 className="text-xl font-bold mb-4">Quick Lookup</h2>
        <div className="space-y-4">
          <input
            type="text"
            placeholder="Enter hash, URL, or domain"
            className="w-full p-3 bg-zinc-700 rounded-lg border border-zinc-600 focus:border-cyan-400 outline-none"
          />
          <button className="bg-cyan-600 hover:bg-cyan-700 text-white px-4 py-2 rounded-lg">
            <Search className="w-4 h-4 mr-2 inline" />
            Check Reputation
          </button>
        </div>
      </div>
    </div>
  )
}

export default VirusTotal
