/**
 * InvestigationNotebook — Cell-based investigation documentation.
 *
 * Features:
 * - Create/list/open notebooks
 * - Markdown + query cells with add/edit/delete
 * - Real-time save on cell changes
 * - Link notebooks to hunts/cases
 */

import React, { useEffect, useState, useCallback } from 'react';
import {
  Box, Typography, Paper, Button, IconButton, TextField, Chip,
  Stack, Divider, Select, MenuItem, FormControl, InputLabel,
  Dialog, DialogTitle, DialogContent, DialogActions,
  Card, CardContent, CardActions, Tooltip, ToggleButton, ToggleButtonGroup,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import SaveIcon from '@mui/icons-material/Save';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import CodeIcon from '@mui/icons-material/Code';
import NotesIcon from '@mui/icons-material/Notes';
import SearchIcon from '@mui/icons-material/Search';
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward';
import ArrowDownwardIcon from '@mui/icons-material/ArrowDownward';
import { useSnackbar } from 'notistack';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  notebooks, hunts,
  NotebookData, NotebookCell, Hunt,
} from '../api/client';

const CELL_TYPE_ICONS: Record<string, React.ReactNode> = {
  markdown: <NotesIcon fontSize="small" />,
  query: <SearchIcon fontSize="small" />,
  code: <CodeIcon fontSize="small" />,
};

export default function InvestigationNotebook() {
  const { enqueueSnackbar } = useSnackbar();

  // List view state
  const [nbList, setNbList] = useState<NotebookData[]>([]);
  const [huntList, setHuntList] = useState<Hunt[]>([]);
  const [huntFilter, setHuntFilter] = useState('');

  // Detail view state
  const [activeNb, setActiveNb] = useState<NotebookData | null>(null);
  const [editingCell, setEditingCell] = useState<string | null>(null);
  const [cellSource, setCellSource] = useState('');

  // Create dialog
  const [createOpen, setCreateOpen] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [newDesc, setNewDesc] = useState('');
  const [newHunt, setNewHunt] = useState('');

  // ── Load ───────────────────────────────────────────────────────────

  const loadList = useCallback(async () => {
    try {
      const opts: any = {};
      if (huntFilter) opts.hunt_id = huntFilter;
      const res = await notebooks.list(opts);
      setNbList(res.notebooks);
    } catch (e: any) {
      enqueueSnackbar(e.message, { variant: 'error' });
    }
  }, [huntFilter, enqueueSnackbar]);

  useEffect(() => {
    hunts.list().then(r => setHuntList(r.hunts)).catch(() => {});
  }, []);

  useEffect(() => { loadList(); }, [loadList]);

  // ── Create ─────────────────────────────────────────────────────────

  const createNotebook = async () => {
    if (!newTitle) return;
    try {
      const nb = await notebooks.create({
        title: newTitle,
        description: newDesc || undefined,
        hunt_id: newHunt || undefined,
      });
      enqueueSnackbar('Notebook created', { variant: 'success' });
      setCreateOpen(false);
      setNewTitle(''); setNewDesc(''); setNewHunt('');
      setActiveNb(nb);
    } catch (e: any) {
      enqueueSnackbar(e.message, { variant: 'error' });
    }
  };

  // ── Open ───────────────────────────────────────────────────────────

  const openNotebook = async (id: string) => {
    try {
      const nb = await notebooks.get(id);
      setActiveNb(nb);
      setEditingCell(null);
    } catch (e: any) {
      enqueueSnackbar(e.message, { variant: 'error' });
    }
  };

  const refreshNotebook = async () => {
    if (!activeNb) return;
    try {
      const nb = await notebooks.get(activeNb.id);
      setActiveNb(nb);
    } catch {}
  };

  // ── Cell operations ────────────────────────────────────────────────

  const addCell = async (type: string) => {
    if (!activeNb) return;
    const cellId = `cell-${Date.now()}`;
    const placeholder = type === 'markdown'
      ? '## New section\n\nWrite your notes here...'
      : type === 'query'
        ? '# Search query\nprocess_name:powershell.exe'
        : '# Code cell\n';
    try {
      const nb = await notebooks.upsertCell(activeNb.id, {
        cell_id: cellId,
        cell_type: type,
        source: placeholder,
      });
      setActiveNb(nb);
      setEditingCell(cellId);
      setCellSource(placeholder);
    } catch (e: any) {
      enqueueSnackbar(e.message, { variant: 'error' });
    }
  };

  const saveCell = async (cellId: string) => {
    if (!activeNb) return;
    try {
      const nb = await notebooks.upsertCell(activeNb.id, {
        cell_id: cellId,
        source: cellSource,
      });
      setActiveNb(nb);
      setEditingCell(null);
    } catch (e: any) {
      enqueueSnackbar(e.message, { variant: 'error' });
    }
  };

  const deleteCell = async (cellId: string) => {
    if (!activeNb) return;
    try {
      await notebooks.deleteCell(activeNb.id, cellId);
      refreshNotebook();
    } catch (e: any) {
      enqueueSnackbar(e.message, { variant: 'error' });
    }
  };

  const moveCell = async (cellId: string, direction: 'up' | 'down') => {
    if (!activeNb) return;
    const cells = [...activeNb.cells];
    const idx = cells.findIndex(c => c.id === cellId);
    if (idx < 0) return;
    const targetIdx = direction === 'up' ? idx - 1 : idx + 1;
    if (targetIdx < 0 || targetIdx >= cells.length) return;
    [cells[idx], cells[targetIdx]] = [cells[targetIdx], cells[idx]];
    try {
      const nb = await notebooks.update(activeNb.id, { cells });
      setActiveNb(nb);
    } catch (e: any) {
      enqueueSnackbar(e.message, { variant: 'error' });
    }
  };

  const deleteNotebook = async (id: string) => {
    try {
      await notebooks.delete(id);
      enqueueSnackbar('Notebook deleted', { variant: 'success' });
      if (activeNb?.id === id) setActiveNb(null);
      loadList();
    } catch (e: any) {
      enqueueSnackbar(e.message, { variant: 'error' });
    }
  };

  // ── Cell renderer ──────────────────────────────────────────────────

  const renderCell = (cell: NotebookCell, index: number) => {
    const isEditing = editingCell === cell.id;
    return (
      <Paper key={cell.id} variant="outlined" sx={{ mb: 1, position: 'relative' }}>
        {/* Cell header */}
        <Stack direction="row" alignItems="center" sx={{ px: 1, py: 0.5, bgcolor: 'action.hover' }}>
          {CELL_TYPE_ICONS[cell.cell_type] || <NotesIcon fontSize="small" />}
          <Typography variant="caption" sx={{ ml: 0.5, flexGrow: 1 }}>
            {cell.cell_type} • #{index + 1}
          </Typography>
          <Tooltip title="Move up"><IconButton size="small" onClick={() => moveCell(cell.id, 'up')} disabled={index === 0}><ArrowUpwardIcon fontSize="small" /></IconButton></Tooltip>
          <Tooltip title="Move down"><IconButton size="small" onClick={() => moveCell(cell.id, 'down')} disabled={index === (activeNb?.cells.length || 0) - 1}><ArrowDownwardIcon fontSize="small" /></IconButton></Tooltip>
          {!isEditing && (
            <Tooltip title="Edit"><IconButton size="small" onClick={() => { setEditingCell(cell.id); setCellSource(cell.source); }}><EditIcon fontSize="small" /></IconButton></Tooltip>
          )}
          {isEditing && (
            <Tooltip title="Save"><IconButton size="small" color="primary" onClick={() => saveCell(cell.id)}><SaveIcon fontSize="small" /></IconButton></Tooltip>
          )}
          <Tooltip title="Delete"><IconButton size="small" color="error" onClick={() => deleteCell(cell.id)}><DeleteIcon fontSize="small" /></IconButton></Tooltip>
        </Stack>
        <Divider />

        {/* Cell body */}
        <Box sx={{ p: 2 }}>
          {isEditing ? (
            <TextField
              multiline fullWidth
              minRows={4}
              value={cellSource}
              onChange={e => setCellSource(e.target.value)}
              onKeyDown={e => { if (e.ctrlKey && e.key === 's') { e.preventDefault(); saveCell(cell.id); } }}
              placeholder="Type here... (Ctrl+S to save)"
              sx={{ fontFamily: cell.cell_type !== 'markdown' ? 'monospace' : undefined }}
            />
          ) : cell.cell_type === 'markdown' ? (
            <Box sx={{ '& h1,& h2,& h3': { mt: 1, mb: 0.5 }, '& p': { mb: 1 }, '& code': { bgcolor: 'action.hover', px: 0.5, borderRadius: 0.5 } }}>
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{cell.source}</ReactMarkdown>
            </Box>
          ) : (
            <pre style={{ margin: 0, fontFamily: 'monospace', fontSize: '0.85rem', whiteSpace: 'pre-wrap', color: '#e0e0e0', backgroundColor: '#1e1e1e', padding: '12px', borderRadius: '4px' }}>
              {cell.source}
            </pre>
          )}
        </Box>

        {/* Cell output */}
        {cell.output && (
          <>
            <Divider />
            <Box sx={{ p: 1, bgcolor: 'grey.900' }}>
              <Typography variant="caption" color="text.secondary">Output:</Typography>
              <pre style={{ margin: 0, fontSize: '0.8rem', whiteSpace: 'pre-wrap' }}>{cell.output}</pre>
            </Box>
          </>
        )}
      </Paper>
    );
  };

  // ── Detail view ────────────────────────────────────────────────────

  if (activeNb) {
    return (
      <Box>
        <Stack direction="row" alignItems="center" spacing={2} mb={2}>
          <Button startIcon={<ArrowBackIcon />} onClick={() => { setActiveNb(null); loadList(); }}>
            Back
          </Button>
          <Typography variant="h5" sx={{ flexGrow: 1 }}>{activeNb.title}</Typography>
          <Chip label={`${activeNb.cells.length} cells`} size="small" />
          <Typography variant="caption" color="text.secondary">
            Updated: {new Date(activeNb.updated_at).toLocaleString()}
          </Typography>
        </Stack>

        {activeNb.description && (
          <Typography variant="body2" color="text.secondary" mb={2}>{activeNb.description}</Typography>
        )}

        {/* Cells */}
        {activeNb.cells.map((cell, i) => renderCell(cell, i))}

        {/* Add cell toolbar */}
        <Paper variant="outlined" sx={{ p: 1, mt: 1, textAlign: 'center' }}>
          <Stack direction="row" spacing={1} justifyContent="center">
            <Button size="small" startIcon={<NotesIcon />} onClick={() => addCell('markdown')}>
              + Markdown
            </Button>
            <Button size="small" startIcon={<SearchIcon />} onClick={() => addCell('query')}>
              + Query
            </Button>
            <Button size="small" startIcon={<CodeIcon />} onClick={() => addCell('code')}>
              + Code
            </Button>
          </Stack>
        </Paper>
      </Box>
    );
  }

  // ── List view ──────────────────────────────────────────────────────

  return (
    <Box>
      <Stack direction="row" justifyContent="space-between" alignItems="center" mb={2}>
        <Typography variant="h5">Investigation Notebooks</Typography>
        <Button variant="contained" startIcon={<AddIcon />} onClick={() => setCreateOpen(true)}>
          New Notebook
        </Button>
      </Stack>

      <Stack direction="row" spacing={2} mb={2}>
        <FormControl size="small" sx={{ minWidth: 200 }}>
          <InputLabel>Filter by Hunt</InputLabel>
          <Select value={huntFilter} label="Filter by Hunt" onChange={e => setHuntFilter(e.target.value)}>
            <MenuItem value="">All</MenuItem>
            {huntList.map(h => <MenuItem key={h.id} value={h.id}>{h.name}</MenuItem>)}
          </Select>
        </FormControl>
      </Stack>

      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 2 }}>
        {nbList.map(nb => (
          <Card key={nb.id} variant="outlined">
            <CardContent>
              <Typography variant="h6" gutterBottom>{nb.title}</Typography>
              {nb.description && (
                <Typography variant="body2" color="text.secondary" gutterBottom>{nb.description}</Typography>
              )}
              <Stack direction="row" spacing={1} flexWrap="wrap">
                <Chip label={`${nb.cell_count} cells`} size="small" />
                {nb.tags?.map((t, i) => <Chip key={i} label={t} size="small" variant="outlined" />)}
              </Stack>
              <Typography variant="caption" color="text.secondary" display="block" mt={1}>
                Updated: {new Date(nb.updated_at).toLocaleString()}
              </Typography>
            </CardContent>
            <CardActions>
              <Button size="small" onClick={() => openNotebook(nb.id)}>Open</Button>
              <IconButton size="small" color="error" onClick={() => deleteNotebook(nb.id)}>
                <DeleteIcon fontSize="small" />
              </IconButton>
            </CardActions>
          </Card>
        ))}
      </Box>

      {nbList.length === 0 && (
        <Typography color="text.secondary" textAlign="center" py={6}>
          No notebooks yet. Create one to start documenting your investigation.
        </Typography>
      )}

      {/* Create dialog */}
      <Dialog open={createOpen} onClose={() => setCreateOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Create Notebook</DialogTitle>
        <DialogContent>
          <Stack spacing={2} mt={1}>
            <TextField label="Title" fullWidth required value={newTitle} onChange={e => setNewTitle(e.target.value)} />
            <TextField label="Description" fullWidth multiline rows={2} value={newDesc} onChange={e => setNewDesc(e.target.value)} />
            <FormControl fullWidth>
              <InputLabel>Linked Hunt</InputLabel>
              <Select value={newHunt} label="Linked Hunt" onChange={e => setNewHunt(e.target.value)}>
                <MenuItem value="">None</MenuItem>
                {huntList.map(h => <MenuItem key={h.id} value={h.id}>{h.name}</MenuItem>)}
              </Select>
            </FormControl>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={createNotebook} disabled={!newTitle}>Create</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
