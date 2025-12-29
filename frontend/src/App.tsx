/**
 * Main ThreatHunt application entry point.
 */

import React, { useState } from "react";
import "./App.css";
import AgentPanel from "./components/AgentPanel";

function App() {
  // Sample state for demonstration
  const [currentDataset] = useState("FileList-2025-12-26");
  const [currentHost] = useState("DESKTOP-ABC123");
  const [currentArtifact] = useState("FileList");
  const [dataDescription] = useState(
    "File listing from system scan showing recent modifications"
  );

  const handleAnalysisAction = (action: string) => {
    console.log("Analysis action triggered:", action);
    // In a real app, this would update the analysis view or apply filters
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1>ThreatHunt - Analyst-Assist Platform</h1>
        <p className="subtitle">
          Powered by agent guidance for faster threat hunting
        </p>
      </header>

      <main className="app-main">
        <div className="app-content">
          <section className="main-panel">
            <h2>Analysis Dashboard</h2>
            <p className="placeholder-text">
              [Main analysis interface would display here]
            </p>
            <div className="data-view">
              <table className="sample-data">
                <thead>
                  <tr>
                    <th>File</th>
                    <th>Modified</th>
                    <th>Size</th>
                    <th>Hash</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>System32\drivers\etc\hosts</td>
                    <td>2025-12-20 14:32</td>
                    <td>456 B</td>
                    <td>d41d8cd98f00b204...</td>
                  </tr>
                  <tr>
                    <td>Windows\Temp\cache.bin</td>
                    <td>2025-12-26 09:15</td>
                    <td>2.3 MB</td>
                    <td>5d41402abc4b2a76...</td>
                  </tr>
                  <tr>
                    <td>Users\Admin\AppData\Roaming\config.xml</td>
                    <td>2025-12-25 16:45</td>
                    <td>12.4 KB</td>
                    <td>e99a18c428cb38d5...</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <aside className="agent-sidebar">
            <AgentPanel
              dataset_name={currentDataset}
              artifact_type={currentArtifact}
              host_identifier={currentHost}
              data_summary={dataDescription}
              onAnalysisAction={handleAnalysisAction}
            />
          </aside>
        </div>
      </main>

      <footer className="app-footer">
        <div className="footer-content">
          <div className="footer-section">
            <h4>About Analyst-Assist Agent</h4>
            <p>
              The agent provides advisory guidance on artifact data, analytical
              pivots, and hypotheses. All decisions remain with the analyst.
            </p>
          </div>
          <div className="footer-section">
            <h4>Capabilities</h4>
            <ul>
              <li>Interpret CSV artifact data</li>
              <li>Suggest analytical directions</li>
              <li>Highlight anomalies</li>
              <li>Propose investigative steps</li>
            </ul>
          </div>
          <div className="footer-section">
            <h4>Governance</h4>
            <ul>
              <li>Read-only guidance</li>
              <li>No tool execution</li>
              <li>No autonomous actions</li>
              <li>Analyst controls decisions</li>
            </ul>
          </div>
        </div>
        <div className="footer-bottom">
          <p>
            &copy; 2025 ThreatHunt. Agent guidance is advisory only. All
            analytical decisions remain with the analyst.
          </p>
        </div>
      </footer>
    </div>
  );
}

export default App;
