import React, { Suspense, useState, useEffect } from "react";
import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";
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
import LoginPage from "./pages/LoginPage";
import Dashboard from "./pages/Dashboard";
import HuntPage from "./pages/HuntPage";

const theme = createTheme({
  palette: {
    mode: "dark",
  },
});

function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (token) {
      // Verify token and get user info
      // For now, just set a dummy user
      setUser({ username: "User" });
    }
    setLoading(false);
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-zinc-900 flex items-center justify-center">
        <div className="text-white">Loading...</div>
      </div>
    );
  }

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Router>
        <div className="flex h-screen bg-zinc-900 text-white">
          <Sidebar />
          <main className="flex-1 p-6 overflow-auto">
            <Suspense fallback={<div className="text-white">Loading...</div>}>
              <Routes>
                <Route path="/login" element={!user ? <LoginPage onLogin={setUser} /> : <Navigate to="/dashboard" />} />
                <Route path="/dashboard" element={user ? <Dashboard user={user} /> : <Navigate to="/login" />} />
                <Route path="/hunt/:huntId" element={user ? <HuntPage user={user} /> : <Navigate to="/login" />} />
                <Route path="/" element={<Navigate to={user ? "/dashboard" : "/login"} />} />
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



