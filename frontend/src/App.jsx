import React, { Suspense, useMemo, lazy } from "react";
import { createTheme, ThemeProvider } from "@mui/material/styles";
import { CssBaseline } from "@mui/material";
import { BrowserRouter as Router, Routes, Route } from "react-router";

import Sidebar from "./components/Sidebar";
const HomePage = lazy(() => import("./pages/HomePage"));
const Baseline = lazy(() => import("./pages/BaselinePage"));
const Networking = lazy(() => import("./pages/NetworkingPage"));
const Applications = lazy(() => import("./pages/ApplicationsPage"));
const SecurityTools = lazy(() => import("./pages/SecurityToolsPage"));
const CSVProcessing = lazy(() => import("./pages/CSVProcessingPage"));
const SettingsConfig = lazy(() => import("./pages/SettingsConfigPage"));
const VirusTotal = lazy(() => import("./pages/VirusTotalPage"));

function App() {
  const theme = useMemo(
    () =>
      createTheme({
        palette: {
          mode: "dark",
        },
      }),
    []
  );

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <div className="flex h-screen bg-zinc-900 text-white">
        <Router>
          <Sidebar />
          <main className="flex-1 p-6 overflow-auto">
            <Suspense fallback={<div>Loading...</div>}>
              <Routes>
                <Route path="/" element={<HomePage />} />
                <Route path="/baseline" element={<Baseline />} />
                <Route path="/networking" element={<Networking />} />
                <Route path="/applications" element={<Applications />} />
                <Route path="/csv-processing" element={<CSVProcessing />} />
                <Route path="/settings" element={<SettingsConfig />} />
                <Route path="/virus-total" element={<VirusTotal />} />
                <Route path="/security-tools" element={<SecurityTools />} />
              </Routes>
            </Suspense>
          </main>
        </Router>
      </div>
    </ThemeProvider>
  );
}

export default App;
