/**
 * AgentPanel — analyst-assist chat with quick / deep / debate modes,
 * streaming support, SANS references, and conversation persistence.
 */

import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  Box, Typography, Paper, TextField, Button, Stack, Chip,
  ToggleButtonGroup, ToggleButton, CircularProgress, Alert,
  Accordion, AccordionSummary, AccordionDetails, Divider, Select,
  MenuItem, FormControl, InputLabel, LinearProgress,
} from '@mui/material';
import SendIcon from '@mui/icons-material/Send';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import SchoolIcon from '@mui/icons-material/School';
import PsychologyIcon from '@mui/icons-material/Psychology';
import ForumIcon from '@mui/icons-material/Forum';
import SpeedIcon from '@mui/icons-material/Speed';
import { useSnackbar } from 'notistack';
import {
  agent, datasets, hunts, type AssistRequest, type AssistResponse,
  type DatasetSummary, type Hunt,
} from '../api/client';

interface Message { role: 'user' | 'assistant'; content: string; meta?: AssistResponse }

export default function AgentPanel() {
  const { enqueueSnackbar } = useSnackbar();
  const [messages, setMessages] = useState<Message[]>([]);
  const [query, setQuery] = useState('');
  const [mode, setMode] = useState<'quick' | 'deep' | 'debate'>('quick');
  const [loading, setLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [datasetList, setDatasets] = useState<DatasetSummary[]>([]);
  const [huntList, setHunts] = useState<Hunt[]>([]);
  const [selectedDataset, setSelectedDataset] = useState('');
  const [selectedHunt, setSelectedHunt] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    datasets.list(0, 100).then(r => setDatasets(r.datasets)).catch(() => {});
    hunts.list(0, 100).then(r => setHunts(r.hunts)).catch(() => {});
  }, []);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  const send = useCallback(async () => {
    if (!query.trim() || loading) return;
    const userMsg: Message = { role: 'user', content: query };
    setMessages(prev => [...prev, userMsg]);
    setQuery('');
    setLoading(true);

    const ds = datasetList.find(d => d.id === selectedDataset);
    const req: AssistRequest = {
      query,
      mode,
      conversation_id: conversationId || undefined,
      hunt_id: selectedHunt || undefined,
      dataset_name: ds?.name,
      data_summary: ds ? `${ds.row_count} rows, columns: ${Object.keys(ds.column_schema || {}).join(', ')}` : undefined,
    };

    try {
      const resp = await agent.assist(req);
      setConversationId(resp.conversation_id || null);
      setMessages(prev => [...prev, { role: 'assistant', content: resp.guidance, meta: resp }]);
    } catch (e: any) {
      enqueueSnackbar(e.message, { variant: 'error' });
      setMessages(prev => [...prev, { role: 'assistant', content: `Error: ${e.message}` }]);
    }
    setLoading(false);
  }, [query, mode, loading, conversationId, selectedDataset, selectedHunt, datasetList, enqueueSnackbar]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
  };

  const newConversation = () => { setMessages([]); setConversationId(null); };

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 1 }}>
        <Typography variant="h5">Agent Assist</Typography>
        <Button size="small" onClick={newConversation}>New Conversation</Button>
      </Stack>

      {/* Controls */}
      <Paper sx={{ p: 1.5, mb: 1 }}>
        <Stack direction="row" spacing={1.5} alignItems="center" flexWrap="wrap">
          <ToggleButtonGroup
            size="small" exclusive value={mode}
            onChange={(_, v) => v && setMode(v)}
          >
            <ToggleButton value="quick"><SpeedIcon sx={{ mr: 0.5, fontSize: 18 }} />Quick</ToggleButton>
            <ToggleButton value="deep"><PsychologyIcon sx={{ mr: 0.5, fontSize: 18 }} />Deep</ToggleButton>
            <ToggleButton value="debate"><ForumIcon sx={{ mr: 0.5, fontSize: 18 }} />Debate</ToggleButton>
          </ToggleButtonGroup>

          <FormControl size="small" sx={{ minWidth: 160 }}>
            <InputLabel>Dataset</InputLabel>
            <Select label="Dataset" value={selectedDataset} onChange={e => setSelectedDataset(e.target.value)}>
              <MenuItem value="">None</MenuItem>
              {datasetList.map(d => <MenuItem key={d.id} value={d.id}>{d.name}</MenuItem>)}
            </Select>
          </FormControl>

          <FormControl size="small" sx={{ minWidth: 160 }}>
            <InputLabel>Hunt</InputLabel>
            <Select label="Hunt" value={selectedHunt} onChange={e => setSelectedHunt(e.target.value)}>
              <MenuItem value="">None</MenuItem>
              {huntList.map(h => <MenuItem key={h.id} value={h.id}>{h.name}</MenuItem>)}
            </Select>
          </FormControl>
        </Stack>
      </Paper>

      {/* Messages */}
      <Paper sx={{ flex: 1, overflow: 'auto', p: 2, mb: 1, minHeight: 300 }}>
        {messages.length === 0 && (
          <Box sx={{ textAlign: 'center', mt: 8 }}>
            <PsychologyIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 1 }} />
            <Typography color="text.secondary">
              Ask a question about your threat hunt data.
            </Typography>
            <Typography variant="caption" color="text.secondary">
              The agent provides advisory guidance — all decisions remain with the analyst.
            </Typography>
          </Box>
        )}
        {messages.map((m, i) => (
          <Box key={i} sx={{ mb: 2 }}>
            <Typography variant="caption" color="text.secondary" fontWeight={700}>
              {m.role === 'user' ? 'You' : 'Agent'}
            </Typography>
            <Paper sx={{
              p: 1.5, mt: 0.5,
              bgcolor: m.role === 'user' ? 'primary.dark' : 'background.default',
              borderColor: m.role === 'user' ? 'primary.main' : 'divider',
            }}>
              <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>{m.content}</Typography>
            </Paper>

            {/* Response metadata */}
            {m.meta && (
              <Box sx={{ mt: 0.5 }}>
                <Stack direction="row" spacing={0.5} flexWrap="wrap" sx={{ mb: 0.5 }}>
                  <Chip label={`${m.meta.confidence * 100}% confidence`} size="small"
                    color={m.meta.confidence >= 0.7 ? 'success' : m.meta.confidence >= 0.4 ? 'warning' : 'error'} variant="outlined" />
                  <Chip label={m.meta.model_used} size="small" variant="outlined" />
                  <Chip label={m.meta.node_used} size="small" variant="outlined" />
                  <Chip label={`${m.meta.latency_ms}ms`} size="small" variant="outlined" />
                </Stack>

                {/* Pivots & Filters */}
                {(m.meta.suggested_pivots.length > 0 || m.meta.suggested_filters.length > 0) && (
                  <Accordion disableGutters sx={{ mt: 0.5 }}>
                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                      <Typography variant="caption">Pivots & Filters</Typography>
                    </AccordionSummary>
                    <AccordionDetails>
                      {m.meta.suggested_pivots.length > 0 && (
                        <>
                          <Typography variant="caption" fontWeight={600}>Pivots</Typography>
                          <Stack direction="row" spacing={0.5} flexWrap="wrap" sx={{ mb: 1 }}>
                            {m.meta.suggested_pivots.map((p, j) => <Chip key={j} label={p} size="small" color="info" />)}
                          </Stack>
                        </>
                      )}
                      {m.meta.suggested_filters.length > 0 && (
                        <>
                          <Typography variant="caption" fontWeight={600}>Filters</Typography>
                          <Stack direction="row" spacing={0.5} flexWrap="wrap">
                            {m.meta.suggested_filters.map((f, j) => <Chip key={j} label={f} size="small" color="secondary" />)}
                          </Stack>
                        </>
                      )}
                    </AccordionDetails>
                  </Accordion>
                )}

                {/* SANS references */}
                {m.meta.sans_references.length > 0 && (
                  <Accordion disableGutters sx={{ mt: 0.5 }}>
                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                      <Stack direction="row" alignItems="center" spacing={0.5}>
                        <SchoolIcon sx={{ fontSize: 16 }} />
                        <Typography variant="caption">SANS References ({m.meta.sans_references.length})</Typography>
                      </Stack>
                    </AccordionSummary>
                    <AccordionDetails>
                      {m.meta.sans_references.map((r, j) => (
                        <Typography key={j} variant="body2" sx={{ mb: 0.5 }}>• {r}</Typography>
                      ))}
                    </AccordionDetails>
                  </Accordion>
                )}

                {/* Debate perspectives */}
                {m.meta.perspectives && m.meta.perspectives.length > 0 && (
                  <Accordion disableGutters sx={{ mt: 0.5 }}>
                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                      <Typography variant="caption">Debate Perspectives ({m.meta.perspectives.length})</Typography>
                    </AccordionSummary>
                    <AccordionDetails>
                      {m.meta.perspectives.map((p: any, j: number) => (
                        <Box key={j} sx={{ mb: 1 }}>
                          <Chip label={p.role || `Perspective ${j + 1}`} size="small" color="primary" sx={{ mb: 0.5 }} />
                          <Typography variant="body2">{p.argument || p.content || JSON.stringify(p)}</Typography>
                          <Divider sx={{ mt: 1 }} />
                        </Box>
                      ))}
                    </AccordionDetails>
                  </Accordion>
                )}

                {/* Caveats */}
                {m.meta.caveats && (
                  <Alert severity="warning" sx={{ mt: 0.5, py: 0 }}>
                    <Typography variant="caption">{m.meta.caveats}</Typography>
                  </Alert>
                )}
              </Box>
            )}
          </Box>
        ))}
        {loading && <LinearProgress sx={{ mb: 1 }} />}
        <div ref={bottomRef} />
      </Paper>

      {/* Input */}
      <Stack direction="row" spacing={1}>
        <TextField
          fullWidth size="small" multiline maxRows={4}
          placeholder="Ask the agent..."
          value={query} onChange={e => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={loading}
        />
        <Button variant="contained" onClick={send} disabled={loading || !query.trim()}>
          {loading ? <CircularProgress size={20} /> : <SendIcon />}
        </Button>
      </Stack>
    </Box>
  );
}
