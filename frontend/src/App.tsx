/**
 * ThreatHunt  MUI-powered analyst-assist platform.
 */

import React, { useState, useCallback, Suspense } from 'react';
import { BrowserRouter, Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import { ThemeProvider, CssBaseline, Box, AppBar, Toolbar, Typography, IconButton,
  Drawer, List, ListItemButton, ListItemIcon, ListItemText, Divider, Chip,
  CircularProgress } from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import DashboardIcon from '@mui/icons-material/Dashboard';
import SearchIcon from '@mui/icons-material/Search';
import StorageIcon from '@mui/icons-material/Storage';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import SecurityIcon from '@mui/icons-material/Security';
import BookmarkIcon from '@mui/icons-material/Bookmark';
import ScienceIcon from '@mui/icons-material/Science';
import CompareArrowsIcon from '@mui/icons-material/CompareArrows';
import GppMaybeIcon from '@mui/icons-material/GppMaybe';
import HubIcon from '@mui/icons-material/Hub';
import AssessmentIcon from '@mui/icons-material/Assessment';
import TimelineIcon from '@mui/icons-material/Timeline';
import PlaylistAddCheckIcon from '@mui/icons-material/PlaylistAddCheck';
import BookmarksIcon from '@mui/icons-material/Bookmarks';
import ShieldIcon from '@mui/icons-material/Shield';
import { SnackbarProvider } from 'notistack';
import theme from './theme';

/* -- Eager imports (lightweight, always needed) -- */
import Dashboard from './components/Dashboard';
import HuntManager from './components/HuntManager';
import DatasetViewer from './components/DatasetViewer';
import FileUpload from './components/FileUpload';
import AgentPanel from './components/AgentPanel';
import EnrichmentPanel from './components/EnrichmentPanel';
import AnnotationPanel from './components/AnnotationPanel';
import HypothesisTracker from './components/HypothesisTracker';
import CorrelationView from './components/CorrelationView';
import AUPScanner from './components/AUPScanner';

/* -- Lazy imports (heavy: charts, network graph, new feature pages) -- */
const NetworkMap = React.lazy(() => import('./components/NetworkMap'));
const AnalysisDashboard = React.lazy(() => import('./components/AnalysisDashboard'));
const MitreMatrix = React.lazy(() => import('./components/MitreMatrix'));
const TimelineView = React.lazy(() => import('./components/TimelineView'));
const PlaybookManager = React.lazy(() => import('./components/PlaybookManager'));
const SavedSearches = React.lazy(() => import('./components/SavedSearches'));

const DRAWER_WIDTH = 240;

interface NavItem { label: string; path: string; icon: React.ReactNode }

const NAV: NavItem[] = [
  { label: 'Dashboard',       path: '/',              icon: <DashboardIcon /> },
  { label: 'Hunts',           path: '/hunts',         icon: <SearchIcon /> },
  { label: 'Datasets',        path: '/datasets',      icon: <StorageIcon /> },
  { label: 'Upload',          path: '/upload',        icon: <UploadFileIcon /> },
  { label: 'AI Analysis',     path: '/analysis',      icon: <AssessmentIcon /> },
  { label: 'Agent',           path: '/agent',         icon: <SmartToyIcon /> },
  { label: 'Enrichment',      path: '/enrichment',    icon: <SecurityIcon /> },
  { label: 'Annotations',     path: '/annotations',   icon: <BookmarkIcon /> },
  { label: 'Hypotheses',      path: '/hypotheses',    icon: <ScienceIcon /> },
  { label: 'Correlation',     path: '/correlation',   icon: <CompareArrowsIcon /> },
  { label: 'Network Map',     path: '/network',       icon: <HubIcon /> },
  { label: 'AUP Scanner',     path: '/aup',           icon: <GppMaybeIcon /> },
  { label: 'MITRE Matrix',    path: '/mitre',         icon: <ShieldIcon /> },
  { label: 'Timeline',        path: '/timeline',      icon: <TimelineIcon /> },
  { label: 'Playbooks',       path: '/playbooks',     icon: <PlaylistAddCheckIcon /> },
  { label: 'Saved Searches',  path: '/saved-searches', icon: <BookmarksIcon /> },
];

function LazyFallback() {
  return (
    <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 200 }}>
      <CircularProgress />
    </Box>
  );
}

function Shell() {
  const [open, setOpen] = useState(true);
  const navigate = useNavigate();
  const location = useLocation();

  const toggle = useCallback(() => setOpen(o => !o), []);

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh' }}>
      {/* App bar */}
      <AppBar position="fixed" sx={{ zIndex: t => t.zIndex.drawer + 1 }}>
        <Toolbar variant="dense">
          <IconButton edge="start" color="inherit" onClick={toggle} sx={{ mr: 1 }}>
            <MenuIcon />
          </IconButton>
          <Typography variant="h6" noWrap sx={{ flexGrow: 1 }}>
            ThreatHunt
          </Typography>
          <Chip label="v0.4.0" size="small" color="primary" variant="outlined" />
        </Toolbar>
      </AppBar>

      {/* Sidebar drawer */}
      <Drawer
        variant="persistent"
        open={open}
        sx={{
          width: open ? DRAWER_WIDTH : 0,
          flexShrink: 0,
          '& .MuiDrawer-paper': { width: DRAWER_WIDTH, boxSizing: 'border-box', mt: '48px' },
        }}
      >
        <List dense>
          {NAV.map(item => (
            <ListItemButton
              key={item.path}
              selected={location.pathname === item.path}
              onClick={() => navigate(item.path)}
            >
              <ListItemIcon sx={{ minWidth: 36 }}>{item.icon}</ListItemIcon>
              <ListItemText primary={item.label} />
            </ListItemButton>
          ))}
        </List>
        <Divider />
      </Drawer>

      {/* Main content */}
      <Box component="main" sx={{
        flexGrow: 1, p: 2, mt: '48px',
        ml: open ? 0 : `-${DRAWER_WIDTH}px`,
        transition: 'margin 225ms cubic-bezier(0,0,0.2,1)',
      }}>
        <Suspense fallback={<LazyFallback />}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/hunts" element={<HuntManager />} />
            <Route path="/datasets" element={<DatasetViewer />} />
            <Route path="/upload" element={<FileUpload />} />
            <Route path="/analysis" element={<AnalysisDashboard />} />
            <Route path="/agent" element={<AgentPanel />} />
            <Route path="/enrichment" element={<EnrichmentPanel />} />
            <Route path="/annotations" element={<AnnotationPanel />} />
            <Route path="/hypotheses" element={<HypothesisTracker />} />
            <Route path="/correlation" element={<CorrelationView />} />
            <Route path="/network" element={<NetworkMap />} />
            <Route path="/aup" element={<AUPScanner />} />
            <Route path="/mitre" element={<MitreMatrix />} />
            <Route path="/timeline" element={<TimelineView />} />
            <Route path="/playbooks" element={<PlaybookManager />} />
            <Route path="/saved-searches" element={<SavedSearches />} />
          </Routes>
        </Suspense>
      </Box>
    </Box>
  );
}

function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <SnackbarProvider maxSnack={3} anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}>
        <BrowserRouter>
          <Shell />
        </BrowserRouter>
      </SnackbarProvider>
    </ThemeProvider>
  );
}

export default App;
