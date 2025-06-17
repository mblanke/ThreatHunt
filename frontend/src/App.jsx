import React, { Suspense } from "react";
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import { CssBaseline } from "@mui/material";
import { createTheme, ThemeProvider } from "@mui/material/styles";

import Sidebar from "./components/Sidebar";
import HomePage from "./pages/HomePage";
import Baseline from "./pages/Baseline";
import Networking from "./pages/Networking";
import Applications from "./pages/Applications";
import CSVProcessing from "./pages/CSVProcessing";
import SettingsConfig from "./pages/SettingsConfig";
import VirusTotal from "./pages/VirusTotal";
import SecurityTools from "./pages/SecurityTools";

const theme = createTheme({
  palette: {
    mode: "dark",
  },
});

function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Router>
        <div className="flex h-screen bg-zinc-900 text-white">
          <Sidebar />
          <main className="flex-1 p-6 overflow-auto">
            <Suspense fallback={<div className="text-white">Loading...</div>}>
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
        </div>
      </Router>
    </ThemeProvider>
  );
}

export default App;



