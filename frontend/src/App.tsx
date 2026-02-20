/**
 * ThreatHunt — MUI-powered analyst-assist platform.
 */

import React, { useState, useCallback } from 'react';
import { BrowserRouter, Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import { ThemeProvider, CssBaseline, Box, AppBar, Toolbar, Typography, IconButton,
  Drawer, List, ListItemButton, ListItemIcon, ListItemText, Divider, Chip } from '@mui/material';
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
import DevicesIcon from '@mui/icons-material/Devices';
import AccountTreeIcon from '@mui/icons-material/AccountTree';
import TimelineIcon from '@mui/icons-material/Timeline';
import ManageSearchIcon from '@mui/icons-material/ManageSearch';
import ScheduleIcon from '@mui/icons-material/Schedule';
import ShieldIcon from '@mui/icons-material/Shield';
import BubbleChartIcon from '@mui/icons-material/BubbleChart';
import WorkIcon from '@mui/icons-material/Work';
import NotificationsActiveIcon from '@mui/icons-material/NotificationsActive';
import MenuBookIcon from '@mui/icons-material/MenuBook';
import PlaylistPlayIcon from '@mui/icons-material/PlaylistPlay';
import { SnackbarProvider } from 'notistack';
import theme from './theme';

import Dashboard from './components/Dashboard';
import HuntManager from './components/HuntManager';
import DatasetViewer from './components/DatasetViewer';
import FileUpload from './components/FileUpload';
import AgentPanel from './components/AgentPanel';
import AnalysisPanel from './components/AnalysisPanel';
import AnnotationPanel from './components/AnnotationPanel';
import HypothesisTracker from './components/HypothesisTracker';
import CorrelationView from './components/CorrelationView';
import AUPScanner from './components/AUPScanner';
import NetworkMap from './components/NetworkMap';
import NetworkPicture from './components/NetworkPicture';
import ProcessTree from './components/ProcessTree';
import StorylineGraph from './components/StorylineGraph';
import TimelineScrubber from './components/TimelineScrubber';
import QueryBar from './components/QueryBar';
import MitreMatrix from './components/MitreMatrix';
import KnowledgeGraph from './components/KnowledgeGraph';
import CaseManager from './components/CaseManager';
import AlertPanel from './components/AlertPanel';
import InvestigationNotebook from './components/InvestigationNotebook';
import PlaybookManager from './components/PlaybookManager';

const DRAWER_WIDTH = 240;

interface NavItem { label: string; path: string; icon: React.ReactNode }

const NAV: NavItem[] = [
  { label: 'Dashboard',    path: '/',              icon: <DashboardIcon /> },
  { label: 'Hunts',        path: '/hunts',         icon: <SearchIcon /> },
  { label: 'Datasets',     path: '/datasets',      icon: <StorageIcon /> },
  { label: 'Upload',       path: '/upload',        icon: <UploadFileIcon /> },
  { label: 'Agent',        path: '/agent',         icon: <SmartToyIcon /> },
  { label: 'Analysis',     path: '/analysis',      icon: <SecurityIcon /> },
  { label: 'Annotations',  path: '/annotations',   icon: <BookmarkIcon /> },
  { label: 'Hypotheses',   path: '/hypotheses',    icon: <ScienceIcon /> },
  { label: 'Correlation',  path: '/correlation',   icon: <CompareArrowsIcon /> },
  { label: 'Network Map',  path: '/network',        icon: <HubIcon /> },
  { label: 'Net Picture',  path: '/netpicture',     icon: <DevicesIcon /> },
  { label: 'Proc Tree',   path: '/proctree',       icon: <AccountTreeIcon /> },
  { label: 'Storyline',   path: '/storyline',      icon: <TimelineIcon /> },
  { label: 'Timeline',    path: '/timeline',       icon: <ScheduleIcon /> },
  { label: 'Search',      path: '/search',         icon: <ManageSearchIcon /> },
  { label: 'MITRE Map',   path: '/mitre',          icon: <ShieldIcon /> },
  { label: 'Knowledge',   path: '/knowledge',      icon: <BubbleChartIcon /> },
  { label: 'Cases',       path: '/cases',          icon: <WorkIcon /> },
  { label: 'Alerts',      path: '/alerts',         icon: <NotificationsActiveIcon /> },
  { label: 'Notebooks',   path: '/notebooks',      icon: <MenuBookIcon /> },
  { label: 'Playbooks',   path: '/playbooks',      icon: <PlaylistPlayIcon /> },
  { label: 'AUP Scanner',  path: '/aup',            icon: <GppMaybeIcon /> },
];

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
          <Chip label="v0.3.0" size="small" color="primary" variant="outlined" />
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
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/hunts" element={<HuntManager />} />
          <Route path="/datasets" element={<DatasetViewer />} />
          <Route path="/upload" element={<FileUpload />} />
          <Route path="/agent" element={<AgentPanel />} />
          <Route path="/analysis" element={<AnalysisPanel />} />
          <Route path="/annotations" element={<AnnotationPanel />} />
          <Route path="/hypotheses" element={<HypothesisTracker />} />
          <Route path="/correlation" element={<CorrelationView />} />
          <Route path="/network" element={<NetworkMap />} />
          <Route path="/netpicture" element={<NetworkPicture />} />
          <Route path="/proctree" element={<ProcessTree />} />
          <Route path="/storyline" element={<StorylineGraph />} />
          <Route path="/timeline" element={<TimelineScrubber />} />
          <Route path="/search" element={<QueryBar />} />
          <Route path="/mitre" element={<MitreMatrix />} />
          <Route path="/knowledge" element={<KnowledgeGraph />} />
          <Route path="/cases" element={<CaseManager />} />
          <Route path="/alerts" element={<AlertPanel />} />
          <Route path="/notebooks" element={<InvestigationNotebook />} />
          <Route path="/playbooks" element={<PlaybookManager />} />
          <Route path="/aup" element={<AUPScanner />} />
        </Routes>
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
