import React, { Suspense, useMemo, lazy } from "react";
import { createTheme, ThemeProvider } from "@mui/material/styles";
import { CssBaseline } from "@mui/material";
import { BrowserRouter, Routes, Route, Navigate } from "react-router";

import Sidebar from "./components/Sidebar";

const HomePage = lazy(() => import("./pages/HomePage"));
const ApplicationsPage = lazy(() => import("./pages/ApplicationsPage"));
const BaselinePage = lazy(() => import("./pages/BaselinePage"));
const CSVProcessingPage = lazy(() => import("./pages/CSVProcessingPage"));
const NetworkingPage = lazy(() => import("./pages/NetworkingPage"));
const SecurityToolsPage = lazy(() => import("./pages/SecurityToolsPage"));
const SettingsConfigPage = lazy(() => import("./pages/SettingsConfigPage"));
const VirusTotalPage = lazy(() => import("./pages/VirusTotalPage"));

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
      
      <BrowserRouter>
        <div className="flex h-screen text-white">
          <Sidebar />
          <div className="flex-1 p-6 overflow-auto">
            <Suspense fallback={<div>Loading...</div>}>
              <Routes>
                <Route index element={<HomePage />} />
                <Route path="/baseline" element={<BaselinePage />} />
                <Route path="/securitytools" element={<SecurityToolsPage />} />
                <Route path="/applications" element={<ApplicationsPage />} />
                <Route path="/csvprocessing" element={<CSVProcessingPage />} />
                <Route path="/networking" element={<NetworkingPage />} />
                <Route path="/settingsconfig" element={<SettingsConfigPage />} />
                <Route path="/virustotal" element={<VirusTotalPage />} />

                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </Suspense>
          </div>
        </div>
      </BrowserRouter>
    </ThemeProvider>
  );
}
export default App;
