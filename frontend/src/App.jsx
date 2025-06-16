import React, { Suspense, useMemo } from "react";
import { createTheme, ThemeProvider } from "@mui/material/styles";
import { CssBaseline } from "@mui/material";
import { BrowserRouter, Routes, Route } from "react-router";

import Sidebar from "./components/Sidebar";
import Baseline from "./components/Baseline";

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
      <div className="flex h-screen text-white">
        <Sidebar />
        <div className="flex-1 p-6 overflow-auto">
          <BrowserRouter>
            <Suspense fallback={<div>Loading...</div>}>
              <Routes>
                <Route path="/baseline" element={<Baseline />} />
              </Routes>
            </Suspense>
          </BrowserRouter>
        </div>
      </div>
    </ThemeProvider>
  );
}
export default App;
