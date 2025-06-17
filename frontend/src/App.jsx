import React from "react";
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import { CssBaseline } from "@mui/material";
import { createTheme, ThemeProvider } from "@mui/material/styles";

import Sidebar from "./components/Sidebar";
import HomePage from "./pages/HomePage";

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
            <Routes>
              <Route path="/" element={<HomePage />} />
            </Routes>
          </main>
        </div>
      </Router>
    </ThemeProvider>
  );
}

export default App;
              <Route path="/applications" element={<Applications />} />
              <Route path="/csv-processing" element={<CSVProcessing />} />
              <Route path="/settings" element={<SettingsConfig />} />
              <Route path="/virus-total" element={<VirusTotal />} />
              <Route path="/security-tools" element={<SecurityTools />} />
            </Routes>
          </main>
        </div>
      </Router>
    </ThemeProvider>
  );
}

export default App;
