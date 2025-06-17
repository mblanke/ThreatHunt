import { Settings, Save, Key } from 'lucide-react'

const SettingsConfig = () => {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold mb-2">Configuration</h1>
        <p className="text-zinc-400">Manage application settings and API keys</p>
      </div>

      <div className="bg-zinc-800 rounded-lg p-6 shadow-lg">
        <h2 className="text-xl font-bold mb-4">API Configuration</h2>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-2">VirusTotal API Key</label>
            <input
              type="password"
              placeholder="Enter API key"
              className="w-full p-3 bg-zinc-700 rounded-lg border border-zinc-600 focus:border-cyan-400 outline-none"
            />
          </div>
          <button className="bg-cyan-600 hover:bg-cyan-700 text-white px-4 py-2 rounded-lg">
            <Save className="w-4 h-4 mr-2 inline" />
            Save Settings
          </button>
        </div>
      </div>
    </div>
  )
}

export default SettingsConfig
