import { Shield, Search, Download } from 'lucide-react'

const SecurityTools = () => {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold mb-2">Security Tools Detection</h1>
        <p className="text-zinc-400">Detect AV, EDR, and VPN tools in uploaded data</p>
      </div>

      <div className="bg-zinc-800 rounded-lg p-6 shadow-lg">
        <h2 className="text-xl font-bold mb-4">Analysis Results</h2>
        <p className="text-zinc-400">Upload a CSV file to analyze security tools</p>
      </div>
    </div>
  )
}

export default SecurityTools
