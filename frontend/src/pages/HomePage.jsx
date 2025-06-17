import React, { useState, useEffect } from 'react';
import { Activity, Upload, FileText, Shield } from 'lucide-react';

const HomePage = () => {
  const [stats, setStats] = useState({
    filesUploaded: 0,
    analysesCompleted: 0,
    threatsDetected: 0
  });

  useEffect(() => {
    // Fetch dashboard stats
    fetch('/api/health')
      .then(res => res.json())
      .then(data => console.log('Backend connected:', data))
      .catch(err => console.error('Backend connection failed:', err));
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold mb-2">Cyber Threat Hunter</h1>
        <p className="text-zinc-400">
          Advanced threat hunting and security analysis platform
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="card">
          <div className="flex items-center">
            <Upload className="w-8 h-8 text-cyan-400 mr-4" />
            <div>
              <h3 className="text-lg font-semibold">Files Uploaded</h3>
              <p className="text-2xl font-bold text-cyan-400">{stats.filesUploaded}</p>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="flex items-center">
            <Activity className="w-8 h-8 text-green-400 mr-4" />
            <div>
              <h3 className="text-lg font-semibold">Analyses Completed</h3>
              <p className="text-2xl font-bold text-green-400">{stats.analysesCompleted}</p>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="flex items-center">
            <Shield className="w-8 h-8 text-red-400 mr-4" />
            <div>
              <h3 className="text-lg font-semibold">Threats Detected</h3>
              <p className="text-2xl font-bold text-red-400">{stats.threatsDetected}</p>
            </div>
          </div>
        </div>
      </div>

      <div className="card">
        <h2 className="text-xl font-bold mb-4">Quick Actions</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <button className="btn-primary flex items-center justify-center">
            <Upload className="w-5 h-5 mr-2" />
            Upload File for Analysis
          </button>
          <button className="btn-secondary flex items-center justify-center">
            <FileText className="w-5 h-5 mr-2" />
            View Recent Reports
          </button>
        </div>
      </div>

      <div className="card">
        <h2 className="text-xl font-bold mb-4">System Health</h2>
        <div className="space-y-2">
          <div className="flex justify-between">
            <span>Backend Status</span>
            <span className="text-green-400">✓ Healthy</span>
          </div>
          <div className="flex justify-between">
            <span>Database Connection</span>
            <span className="text-green-400">✓ Connected</span>
          </div>
          <div className="flex justify-between">
            <span>Storage Available</span>
            <span className="text-yellow-400">⚠ 75% Used</span>
          </div>
        </div>
      </div>

      <div className="bg-zinc-800 rounded-lg p-6 shadow-lg">
        <div className="flex items-center">
          <Shield className="w-8 h-8 text-cyan-400 mr-4" />
          <div>
            <h3 className="text-lg font-semibold">System Status</h3>
            <p className="text-2xl font-bold text-cyan-400">Ready</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default HomePage;
