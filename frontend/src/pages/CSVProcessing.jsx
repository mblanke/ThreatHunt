import { Upload, FileText, Download } from 'lucide-react'

const CSVProcessing = () => {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold mb-2">CSV Processing</h1>
        <p className="text-zinc-400">Upload and analyze CSV files for threat hunting</p>
      </div>

      <div className="bg-zinc-800 rounded-lg p-6 shadow-lg">
        <h2 className="text-xl font-bold mb-4">File Upload</h2>
        <div className="space-y-4">
          <input
            type="file"
            accept=".csv,.txt,.log"
            className="block w-full text-sm text-zinc-400"
          />
          <button className="bg-cyan-600 hover:bg-cyan-700 text-white px-4 py-2 rounded-lg">
            <Upload className="w-4 h-4 mr-2 inline" />
            Upload File
          </button>
        </div>
      </div>
    </div>
  )
}

export default CSVProcessing
