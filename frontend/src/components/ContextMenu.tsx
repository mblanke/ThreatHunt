/**
 * ContextMenu — right-click radial menu for analyst actions on cells / rows.
 * Re-usable across DatasetViewer, NetworkMap, ProcessTree, StorylineGraph, etc.
 *
 * Actions:
 *   - Annotate (open annotation dialog)
 *   - Copy value
 *   - Search for value (navigates to Search page)
 *   - Enrich IOC (stub for future)
 *   - Add to hypothesis
 *   - Mark as suspicious / benign
 */

import React, { useState, useCallback } from 'react';
import {
  Menu, MenuItem, ListItemIcon, ListItemText, Divider,
  Dialog, DialogTitle, DialogContent, DialogActions,
  Button, TextField, FormControl, InputLabel, Select,
  Stack, Typography, Chip,
} from '@mui/material';
import BookmarkAddIcon from '@mui/icons-material/BookmarkAdd';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import SearchIcon from '@mui/icons-material/Search';
import FlagIcon from '@mui/icons-material/Flag';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import ScienceIcon from '@mui/icons-material/Science';
import { useSnackbar } from 'notistack';
import { useNavigate } from 'react-router-dom';
import { annotations } from '../api/client';

// ── Types ────────────────────────────────────────────────────────────

export interface ContextTarget {
  /** The cell / node value the user right-clicked on */
  value: string;
  /** The field / column name */
  field?: string;
  /** Dataset ID if applicable */
  datasetId?: string;
  /** Row index if applicable */
  rowIndex?: number;
  /** Extra context for display */
  extra?: Record<string, any>;
}

interface ContextMenuProps {
  anchorPosition: { top: number; left: number } | null;
  target: ContextTarget | null;
  onClose: () => void;
  /** Optional callback after an annotation is created */
  onAnnotated?: () => void;
}

// ── Severity + Tag options ───────────────────────────────────────────

const SEVERITIES = ['info', 'low', 'medium', 'high', 'critical'] as const;
const TAGS = ['suspicious', 'benign', 'needs-review', 'false-positive', 'true-positive', 'escalate'] as const;
const SEV_COLORS: Record<string, 'default' | 'info' | 'success' | 'warning' | 'error'> = {
  info: 'info', low: 'success', medium: 'warning', high: 'error', critical: 'error',
};

// ── Component ────────────────────────────────────────────────────────

export default function ContextMenu({ anchorPosition, target, onClose, onAnnotated }: ContextMenuProps) {
  const { enqueueSnackbar } = useSnackbar();
  const navigate = useNavigate();
  const [annOpen, setAnnOpen] = useState(false);
  const [form, setForm] = useState({ text: '', severity: 'medium', tag: 'suspicious' });

  const handleCopy = useCallback(() => {
    if (target?.value) {
      navigator.clipboard.writeText(target.value);
      enqueueSnackbar('Copied to clipboard', { variant: 'info' });
    }
    onClose();
  }, [target, enqueueSnackbar, onClose]);

  const handleSearch = useCallback(() => {
    if (target?.value) {
      // Navigate to search page with the value pre-loaded via query param
      navigate(`/search?q=${encodeURIComponent(target.value)}`);
    }
    onClose();
  }, [target, navigate, onClose]);

  const handleQuickAnnotate = useCallback(async (tag: string, severity: string) => {
    if (!target) return;
    try {
      const text = target.field
        ? `${tag}: ${target.field}="${target.value}"`
        : `${tag}: "${target.value}"`;
      await annotations.create({
        text,
        severity,
        tag,
        dataset_id: target.datasetId,
        row_id: target.rowIndex,
      });
      enqueueSnackbar(`Marked as ${tag}`, { variant: 'success' });
      onAnnotated?.();
    } catch (e: any) {
      enqueueSnackbar(e.message, { variant: 'error' });
    }
    onClose();
  }, [target, enqueueSnackbar, onClose, onAnnotated]);

  const handleAnnotateOpen = () => {
    setForm({
      text: target?.field
        ? `${target.field}="${target.value}"`
        : target?.value || '',
      severity: 'medium',
      tag: 'suspicious',
    });
    setAnnOpen(true);
    onClose();
  };

  const handleAnnotateSubmit = async () => {
    if (!target) return;
    try {
      await annotations.create({
        text: form.text,
        severity: form.severity,
        tag: form.tag,
        dataset_id: target.datasetId,
        row_id: target.rowIndex,
      });
      enqueueSnackbar('Annotation created', { variant: 'success' });
      onAnnotated?.();
    } catch (e: any) {
      enqueueSnackbar(e.message, { variant: 'error' });
    }
    setAnnOpen(false);
  };

  const handleHypothesis = () => {
    // Navigate to hypotheses page — user can create there
    navigate('/hypotheses');
    onClose();
  };

  return (
    <>
      {/* Context menu */}
      <Menu
        open={!!anchorPosition}
        onClose={onClose}
        anchorReference="anchorPosition"
        anchorPosition={anchorPosition ?? undefined}
        slotProps={{ paper: { sx: { minWidth: 220 } } }}
      >
        {target && (
          <MenuItem disabled sx={{ opacity: '1 !important', py: 0.5 }}>
            <Typography variant="caption" color="text.secondary" noWrap sx={{ maxWidth: 260 }}>
              {target.field ? `${target.field}: ` : ''}
              <strong>{String(target.value).slice(0, 60)}</strong>
            </Typography>
          </MenuItem>
        )}
        <Divider />

        <MenuItem onClick={handleCopy}>
          <ListItemIcon><ContentCopyIcon fontSize="small" /></ListItemIcon>
          <ListItemText>Copy value</ListItemText>
        </MenuItem>

        <MenuItem onClick={handleSearch}>
          <ListItemIcon><SearchIcon fontSize="small" /></ListItemIcon>
          <ListItemText>Search for this</ListItemText>
        </MenuItem>

        <Divider />

        <MenuItem onClick={handleAnnotateOpen}>
          <ListItemIcon><BookmarkAddIcon fontSize="small" /></ListItemIcon>
          <ListItemText>Annotate…</ListItemText>
        </MenuItem>

        <MenuItem onClick={() => handleQuickAnnotate('suspicious', 'high')}>
          <ListItemIcon><WarningAmberIcon fontSize="small" color="warning" /></ListItemIcon>
          <ListItemText>Mark suspicious</ListItemText>
        </MenuItem>

        <MenuItem onClick={() => handleQuickAnnotate('benign', 'info')}>
          <ListItemIcon><CheckCircleOutlineIcon fontSize="small" color="success" /></ListItemIcon>
          <ListItemText>Mark benign</ListItemText>
        </MenuItem>

        <MenuItem onClick={() => handleQuickAnnotate('escalate', 'critical')}>
          <ListItemIcon><FlagIcon fontSize="small" color="error" /></ListItemIcon>
          <ListItemText>Escalate</ListItemText>
        </MenuItem>

        <Divider />

        <MenuItem onClick={handleHypothesis}>
          <ListItemIcon><ScienceIcon fontSize="small" /></ListItemIcon>
          <ListItemText>Add to hypothesis</ListItemText>
        </MenuItem>
      </Menu>

      {/* Full annotation dialog */}
      <Dialog open={annOpen} onClose={() => setAnnOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>
          Annotate
          {target?.field && (
            <Chip label={target.field} size="small" sx={{ ml: 1 }} />
          )}
        </DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label="Annotation text" fullWidth multiline rows={3}
              value={form.text}
              onChange={e => setForm(f => ({ ...f, text: e.target.value }))}
            />
            <Stack direction="row" spacing={2}>
              <FormControl fullWidth size="small">
                <InputLabel>Severity</InputLabel>
                <Select label="Severity" value={form.severity}
                  onChange={e => setForm(f => ({ ...f, severity: e.target.value }))}>
                  {SEVERITIES.map(s => (
                    <MenuItem key={s} value={s}>
                      <Chip label={s} size="small" color={SEV_COLORS[s] || 'default'} variant="outlined" sx={{ mr: 1 }} />
                      {s}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              <FormControl fullWidth size="small">
                <InputLabel>Tag</InputLabel>
                <Select label="Tag" value={form.tag}
                  onChange={e => setForm(f => ({ ...f, tag: e.target.value }))}>
                  {TAGS.map(t => <MenuItem key={t} value={t}>{t}</MenuItem>)}
                </Select>
              </FormControl>
            </Stack>
            {target?.datasetId && (
              <Typography variant="caption" color="text.secondary">
                Dataset: {target.datasetId}
                {target.rowIndex != null && ` · Row: ${target.rowIndex}`}
              </Typography>
            )}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setAnnOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleAnnotateSubmit} disabled={!form.text.trim()}>
            Create
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}

// ── Hook for easy integration ────────────────────────────────────────

export function useContextMenu() {
  const [menuPos, setMenuPos] = useState<{ top: number; left: number } | null>(null);
  const [menuTarget, setMenuTarget] = useState<ContextTarget | null>(null);

  const openMenu = useCallback((e: React.MouseEvent, target: ContextTarget) => {
    e.preventDefault();
    e.stopPropagation();
    setMenuPos({ top: e.clientY, left: e.clientX });
    setMenuTarget(target);
  }, []);

  const closeMenu = useCallback(() => {
    setMenuPos(null);
    setMenuTarget(null);
  }, []);

  return { menuPos, menuTarget, openMenu, closeMenu };
}
