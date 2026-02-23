/**
 * NetworkPicture — deduplicated host inventory view.
 *
 * Select a hunt → server scans all datasets, groups by hostname,
 * returns one row per unique host with IPs, users, OS, MAC, ports.
 * No duplicates — sets handle dedup. All unique values shown.
 */

import React, { useEffect, useState, useMemo, useCallback } from 'react';
import {
  Box, Typography, Paper, Stack, Alert, Chip, TextField, Tooltip,
  LinearProgress, FormControl, InputLabel, Select, MenuItem,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  TableSortLabel, Collapse, IconButton,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import ComputerIcon from '@mui/icons-material/Computer';
import RouterIcon from '@mui/icons-material/Router';
import PeopleIcon from '@mui/icons-material/People';
import DnsIcon from '@mui/icons-material/Dns';
import {
  hunts, network,
  type Hunt, type HostEntry, type PictureSummary,
} from '../api/client';

// ── Colour palette (matches NetworkMap) ──────────────────────────────

const CHIP_COLORS = {
  ip: '#3b82f6',
  user: '#22c55e',
  os: '#eab308',
  mac: '#8b5cf6',
  port: '#f43f5e',
  proto: '#06b6d4',
};

// ── Collapsible chip list — show first N, expand for all ─────────────

function ChipList({ items, color, max = 5 }: { items: string[]; color: string; max?: number }) {
  const [expanded, setExpanded] = useState(false);
  if (items.length === 0) return <Typography variant="body2" color="text.secondary">—</Typography>;
  const show = expanded ? items : items.slice(0, max);
  const more = items.length - max;
  return (
    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, alignItems: 'center' }}>
      {show.map(v => (
        <Chip
          key={v} label={v} size="small" variant="outlined"
          sx={{ borderColor: color, color, fontSize: '0.75rem', height: 22 }}
        />
      ))}
      {more > 0 && !expanded && (
        <Chip
          label={`+${more} more`} size="small"
          onClick={() => setExpanded(true)}
          sx={{
            bgcolor: color, color: '#fff', fontSize: '0.7rem', height: 22,
            cursor: 'pointer', '&:hover': { opacity: 0.85 },
          }}
        />
      )}
      {expanded && more > 0 && (
        <Chip
          label="less" size="small"
          onClick={() => setExpanded(false)}
          sx={{
            fontSize: '0.7rem', height: 22, cursor: 'pointer',
            '&:hover': { opacity: 0.85 },
          }}
        />
      )}
    </Box>
  );
}

// ── Stat card ────────────────────────────────────────────────────────

function StatCard({ label, value, icon }: { label: string; value: number | string; icon: React.ReactNode }) {
  return (
    <Paper elevation={1} sx={{ px: 2, py: 1.5, minWidth: 140, textAlign: 'center' }}>
      <Stack direction="row" spacing={1} alignItems="center" justifyContent="center">
        {icon}
        <Typography variant="h5" fontWeight={700}>{value}</Typography>
      </Stack>
      <Typography variant="caption" color="text.secondary">{label}</Typography>
    </Paper>
  );
}

// ── Sort helpers ─────────────────────────────────────────────────────

type SortKey = 'hostname' | 'ips' | 'users' | 'connection_count';
type SortDir = 'asc' | 'desc';

function sortHosts(hosts: HostEntry[], key: SortKey, dir: SortDir): HostEntry[] {
  const cmp = (a: HostEntry, b: HostEntry): number => {
    switch (key) {
      case 'hostname': return a.hostname.localeCompare(b.hostname);
      case 'ips': return a.ips.length - b.ips.length;
      case 'users': return a.users.length - b.users.length;
      case 'connection_count': return a.connection_count - b.connection_count;
      default: return 0;
    }
  };
  const sorted = [...hosts].sort(cmp);
  return dir === 'desc' ? sorted.reverse() : sorted;
}

// ── Expanded row detail panel ────────────────────────────────────────

function HostDetail({ host }: { host: HostEntry }) {
  return (
    <Box sx={{ p: 2, bgcolor: 'background.default' }}>
      <Stack spacing={1.5}>
        {host.remote_targets.length > 0 && (
          <Box>
            <Typography variant="subtitle2" gutterBottom>Remote Targets ({host.remote_targets.length})</Typography>
            <ChipList items={host.remote_targets} color={CHIP_COLORS.ip} max={50} />
          </Box>
        )}
        {host.open_ports.length > 0 && (
          <Box>
            <Typography variant="subtitle2" gutterBottom>All Open Ports ({host.open_ports.length})</Typography>
            <ChipList items={host.open_ports} color={CHIP_COLORS.port} max={50} />
          </Box>
        )}
        {host.protocols.length > 0 && (
          <Box>
            <Typography variant="subtitle2" gutterBottom>Protocols</Typography>
            <ChipList items={host.protocols} color={CHIP_COLORS.proto} max={20} />
          </Box>
        )}
        {host.mac_addresses.length > 0 && (
          <Box>
            <Typography variant="subtitle2" gutterBottom>MAC Addresses</Typography>
            <ChipList items={host.mac_addresses} color={CHIP_COLORS.mac} max={20} />
          </Box>
        )}
        <Box>
          <Typography variant="subtitle2" gutterBottom>Datasets</Typography>
          <Typography variant="body2" color="text.secondary">
            {host.datasets.join(', ') || '—'}
          </Typography>
        </Box>
        {(host.first_seen || host.last_seen) && (
          <Box>
            <Typography variant="subtitle2" gutterBottom>Time Range</Typography>
            <Typography variant="body2" color="text.secondary">
              {host.first_seen || '?'} → {host.last_seen || '?'}
            </Typography>
          </Box>
        )}
      </Stack>
    </Box>
  );
}

// ── Main component ───────────────────────────────────────────────────

export default function NetworkPicture() {
  // Hunt selector
  const [huntList, setHuntList] = useState<Hunt[]>([]);
  const [selectedHunt, setSelectedHunt] = useState('');

  // Data
  const [hosts, setHosts] = useState<HostEntry[]>([]);
  const [summary, setSummary] = useState<PictureSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Table state
  const [search, setSearch] = useState('');
  const [sortKey, setSortKey] = useState<SortKey>('connection_count');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  // Load hunts on mount
  useEffect(() => {
    hunts.list(0, 200).then(r => setHuntList(r.hunts)).catch(() => {});
  }, []);

  // Load network picture when hunt changes
  const loadPicture = useCallback(async (huntId: string) => {
    if (!huntId) return;
    setLoading(true);
    setError('');
    setHosts([]);
    setSummary(null);
    setExpandedRow(null);
    try {
      const resp = await network.picture(huntId);
      setHosts(resp.hosts);
      setSummary(resp.summary);
    } catch (e: any) {
      setError(e.message || 'Failed to load network picture');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (selectedHunt) loadPicture(selectedHunt);
  }, [selectedHunt, loadPicture]);

  // Filter + sort
  const filtered = useMemo(() => {
    const q = search.toLowerCase().trim();
    let list = hosts;
    if (q) {
      list = hosts.filter(h =>
        h.hostname.toLowerCase().includes(q) ||
        h.ips.some(ip => ip.includes(q)) ||
        h.users.some(u => u.toLowerCase().includes(q)) ||
        h.os.some(o => o.toLowerCase().includes(q)) ||
        h.mac_addresses.some(m => m.toLowerCase().includes(q))
      );
    }
    return sortHosts(list, sortKey, sortDir);
  }, [hosts, search, sortKey, sortDir]);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortDir(key === 'connection_count' ? 'desc' : 'asc');
    }
  };

  const toggleExpand = (hostname: string) => {
    setExpandedRow(prev => prev === hostname ? null : hostname);
  };

  return (
    <Box>
      <Typography variant="h5" gutterBottom fontWeight={700}>
        Network Picture
      </Typography>
      <Typography variant="body2" color="text.secondary" gutterBottom>
        Deduplicated host inventory — one row per machine. Hostname, IPs, users, OS, MACs aggregated from all datasets.
      </Typography>

      {/* Hunt selector */}
      <Stack direction="row" spacing={2} sx={{ mt: 2, mb: 2 }} alignItems="center">
        <FormControl size="small" sx={{ minWidth: 300 }}>
          <InputLabel>Select Hunt</InputLabel>
          <Select
            value={selectedHunt}
            label="Select Hunt"
            onChange={e => setSelectedHunt(e.target.value)}
          >
            {huntList.map(h => (
              <MenuItem key={h.id} value={h.id}>
                {h.name} ({h.dataset_count} datasets)
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        {selectedHunt && (
          <Tooltip title="Refresh">
            <IconButton onClick={() => loadPicture(selectedHunt)} size="small">
              <RefreshIcon />
            </IconButton>
          </Tooltip>
        )}

        <TextField
          size="small" placeholder="Search hostname, IP, user, OS, MAC…"
          value={search} onChange={e => setSearch(e.target.value)}
          sx={{ minWidth: 280 }}
        />
      </Stack>

      {loading && <LinearProgress sx={{ mb: 2 }} />}
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      {/* Summary stats */}
      {summary && !loading && (
        <Stack direction="row" spacing={2} sx={{ mb: 2 }} flexWrap="wrap" useFlexGap>
          <StatCard label="Hosts" value={summary.total_hosts} icon={<ComputerIcon color="primary" />} />
          <StatCard label="Unique IPs" value={summary.total_unique_ips} icon={<RouterIcon color="secondary" />} />
          <StatCard label="Connections" value={summary.total_connections.toLocaleString()} icon={<DnsIcon color="info" />} />
          <StatCard label="Datasets Scanned" value={summary.datasets_scanned} icon={<PeopleIcon color="success" />} />
          {search && (
            <Paper elevation={1} sx={{ px: 2, py: 1.5, textAlign: 'center' }}>
              <Typography variant="h5" fontWeight={700}>{filtered.length}</Typography>
              <Typography variant="caption" color="text.secondary">Matching filter</Typography>
            </Paper>
          )}
        </Stack>
      )}

      {/* Host table */}
      {!loading && hosts.length > 0 && (
        <TableContainer component={Paper} sx={{ maxHeight: 'calc(100vh - 320px)' }}>
          <Table stickyHeader size="small">
            <TableHead>
              <TableRow>
                <TableCell width={32} />
                <TableCell>
                  <TableSortLabel
                    active={sortKey === 'hostname'} direction={sortKey === 'hostname' ? sortDir : 'asc'}
                    onClick={() => handleSort('hostname')}
                  >
                    Hostname
                  </TableSortLabel>
                </TableCell>
                <TableCell>
                  <TableSortLabel
                    active={sortKey === 'ips'} direction={sortKey === 'ips' ? sortDir : 'asc'}
                    onClick={() => handleSort('ips')}
                  >
                    IPs
                  </TableSortLabel>
                </TableCell>
                <TableCell>
                  <TableSortLabel
                    active={sortKey === 'users'} direction={sortKey === 'users' ? sortDir : 'asc'}
                    onClick={() => handleSort('users')}
                  >
                    Users
                  </TableSortLabel>
                </TableCell>
                <TableCell>OS</TableCell>
                <TableCell>MAC</TableCell>
                <TableCell>
                  <TableSortLabel
                    active={sortKey === 'connection_count'} direction={sortKey === 'connection_count' ? sortDir : 'asc'}
                    onClick={() => handleSort('connection_count')}
                  >
                    Connections
                  </TableSortLabel>
                </TableCell>
                <TableCell>Ports</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {filtered.map(host => {
                const isExpanded = expandedRow === host.hostname;
                return (
                  <React.Fragment key={host.hostname}>
                    <TableRow
                      hover
                      sx={{ cursor: 'pointer', '& > *': { borderBottom: isExpanded ? 'none' : undefined } }}
                      onClick={() => toggleExpand(host.hostname)}
                    >
                      <TableCell>
                        <IconButton size="small">
                          {isExpanded ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
                        </IconButton>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" fontWeight={700}>{host.hostname}</Typography>
                      </TableCell>
                      <TableCell><ChipList items={host.ips} color={CHIP_COLORS.ip} /></TableCell>
                      <TableCell><ChipList items={host.users} color={CHIP_COLORS.user} /></TableCell>
                      <TableCell>
                        {host.os.length > 0
                          ? host.os.join(', ')
                          : <Typography variant="body2" color="text.secondary">—</Typography>}
                      </TableCell>
                      <TableCell><ChipList items={host.mac_addresses} color={CHIP_COLORS.mac} /></TableCell>
                      <TableCell>
                        <Chip
                          label={host.connection_count.toLocaleString()}
                          size="small" color="primary" variant="outlined"
                          sx={{ fontWeight: 700 }}
                        />
                      </TableCell>
                      <TableCell><ChipList items={host.open_ports.slice(0, 5)} color={CHIP_COLORS.port} max={5} /></TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell colSpan={8} sx={{ p: 0, border: 0 }}>
                        <Collapse in={isExpanded} timeout="auto" unmountOnExit>
                          <HostDetail host={host} />
                        </Collapse>
                      </TableCell>
                    </TableRow>
                  </React.Fragment>
                );
              })}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {/* Empty state */}
      {!loading && selectedHunt && hosts.length === 0 && !error && (
        <Alert severity="info" sx={{ mt: 2 }}>
          No hosts found. Upload datasets with hostname/IP columns to this hunt.
        </Alert>
      )}
      {!selectedHunt && (
        <Alert severity="info" sx={{ mt: 2 }}>
          Select a hunt to view the network picture.
        </Alert>
      )}
    </Box>
  );
}
