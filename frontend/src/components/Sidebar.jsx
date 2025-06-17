import React, { useState } from 'react';
import { Link, useLocation } from 'react-router';
import {
  ShieldCheck,
  Server,
  Bug,
  Folder,
  Globe,
  Settings,
  ChevronDown,
  ChevronRight,
} from 'lucide-react';
import AddIcon from '@mui/icons-material/Add';
import BugReportIcon from '@mui/icons-material/BugReport';
import EngineeringIcon from '@mui/icons-material/Engineering';

const SidebarItem = ({ icon: Icon, label, to, children }) => {
  const [isOpen, setIsOpen] = useState(false);
  const location = useLocation();
  const hasChildren = !!children;
  const isActive = location.pathname === to;

  const handleClick = () => {
    if (hasChildren) {
      setIsOpen(!isOpen);
    }
  };

  const itemContent = (
    <div
      className={`sidebar-item ${isActive ? 'bg-zinc-800' : ''}`}
      onClick={handleClick}
    >
      <Icon className="sidebar-icon" />
      <span className="flex-grow">{label}</span>
      {hasChildren && (isOpen ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />)}
    </div>
  );

  return (
    <div className="text-sm">
      {to && !hasChildren ? (
        <Link to={to}>{itemContent}</Link>
      ) : (
        itemContent
      )}
      {hasChildren && isOpen && (
        <div className="ml-8 mt-1 space-y-1 text-zinc-400">
          {children}
        </div>
      )}
    </div>
  );
};

const Sidebar = () => (
  <div className="w-56 h-full bg-zinc-950 p-4 flex flex-col space-y-2 rounded-r-xl shadow-md">
    <h2 className="text-xl font-bold text-white mb-4">Threat Hunt Dashboard</h2>
    <SidebarItem icon={ShieldCheck} label="HomePage" to="/" />
    <SidebarItem icon={Server} label="Baseline" to="/baseline" />
    <SidebarItem icon={Bug} label="Networking" to="/networking" />
    <SidebarItem icon={Folder} label="Applications" to="/applications" />
    <SidebarItem icon={Globe} label="CSV Processing" to="/csv-processing" />
    <SidebarItem
      icon={Settings}
      label="Tools / Configs"
      children={
        <>
          <Link to="/security-tools" className="block hover:text-white">Security Tools</Link>
          <Link to="/settings" className="block hover:text-white">Configuration</Link>
        </>
      }
    />
    <SidebarItem icon={Globe} label="Virus Total" to="/virus-total" />
  </div>
);

export default Sidebar;
