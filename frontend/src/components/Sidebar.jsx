import React, { useState } from 'react';
import { useNavigate } from 'react-router';
import {
  ShieldCheck, Server, Bug, Lock, Globe, Settings,
  ChevronDown, ChevronRight, Folder
} from 'lucide-react';
import AddIcon from '@mui/icons-material/Add';
import BugReportIcon from '@mui/icons-material/BugReport';
import EngineeringIcon from '@mui/icons-material/Engineering';


const SidebarItem = ({ icon: Icon, label, href, children }) => {
  const [open, setOpen] = useState(false);
  const hasChildren = !!children;

  const navigate = useNavigate();

  const handleClick = () => {
    if (hasChildren) {
      setOpen(!open);
    }

    if (href) {
      navigate(href);
    }
  };

  return (
    <div className="text-sm w-full">
      <div
        className="flex items-center justify-between px-4 py-2 cursor-pointer rounded hover:bg-zinc-800 text-white transition-all"
        onClick={handleClick}
      >
        <div className="flex items-center space-x-3">
          <Icon className="w-5 h-5 text-cyan-400" />
          <span>{label}</span>
          {hasChildren &&
            (open ? <AddIcon className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />)}
        </div>

      </div>
      {hasChildren && open && (
        <div className="ml-8 mt-1 space-y-1 text-zinc-400">
          {children}
        </div>
      )}
    </div>
  );
};

const Sidebar = () => (
  <div className="h-screen w-64 shadow-lg p-4 flex flex-col space-y-2">
    <h2 className="text-xl font-bold text-white mb-4">Threat Hunt Dashboard</h2>
    <SidebarItem icon={ShieldCheck} label="HomePage" href="/" />
    <SidebarItem icon={Server} label="Baseline" href="/baseline" />
    <SidebarItem icon={Bug} label="Networking" href="/networking" />
    <SidebarItem icon={Folder} label="Applications" href="/applications" />
    <SidebarItem icon={Globe} label="CSV Processing" href="/csvprocessing" />
    <SidebarItem icon={Settings} label="Security Tools">
      <div>Anti Virus</div>
      <div>Endpoint Detection & Response</div>
      <div>Virtual Private Networks</div>
    </SidebarItem>
    <SidebarItem icon={BugReportIcon} label="Virus Totals" href="/virustotal" />   
    <SidebarItem icon={EngineeringIcon} label="Settings & Config" href="/settingsconfig" />  
  </div>
);

export default Sidebar;
