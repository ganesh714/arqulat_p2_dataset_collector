import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ChevronUp, ChevronDown, Terminal, MessageSquare, Copy } from 'lucide-react';
import api from '../api';

const POLL_INTERVAL = 3000;

// ─── Copy‑prompt template ───────────────────────────────────────────
function buildInstructionsTemplate(categoryName, promptText) {
  return `You are an expert Python developer for Blender (bpy), working on a structured dataset with a fixed format.

Your task is to produce TWO things for the given prompt: a THINK BLOCK and PHASE 2 CODE. Do not include imports, scene setup, or export/render code — those are fixed and added automatically by our system.

===== PART 1: THINK BLOCK =====
A structured reasoning plan with this exact structure:

To create "[EXACT PROMPT TEXT]" procedurally in Blender, I need [1-line high-level approach].

1. Materials:
   - "[MaterialName]": [base color as (R, G, B)], Roughness=[value]. [Shader technique if any].

2. Geometry Strategy: [primitives, modifiers, techniques used].

3. [ComponentName]: [exact dimensions in meters, vertex/segment counts, modifier settings, position as (x,y,z), material used].

4. [ComponentName]: ...
   ... one numbered section per distinct part ...

N. Pipeline: All parts joined into "[FinalObjectName]". Exported as GLB. Rendered with EEVEE_NEXT (EEVEE fallback) at 512x512, transparent background.

Rules:
- Be specific and numerical (e.g. "Legs (4 pieces): cylinders (radius=0.015, depth=0.41) at 45° intervals" — not "create legs using cylinders")
- All dimensions in meters, using realistic furniture scale (chair seat ~0.45m high)
- Use realistic material colors, not pure RGB values

===== PART 2: PHASE 2 CODE =====
Python code for ONLY the materials, helper functions, geometry construction, and final assembly. Follow these rules:
- Do NOT include: import statements, scene setup, camera/light creation, export, or render calls — these are added automatically.
- Define materials using Principled BSDF via bpy.data.materials.new() + use_nodes=True + nodes.get("Principled BSDF")
- Build geometry using bpy.ops.mesh.primitive_*_add(), bmesh, or curves as appropriate. Name every object descriptively. Call shade_smooth() after creating visible objects.
- Collect all created parts in a list called \`parts = []\`
- End with the standard assembly pattern: select all parts, join them, name the result, apply transforms, and ground it at z=0
- The VERY LAST LINE of your code MUST be exactly: final_object_name = "YourObjectVariableName"
  (this must match the Python variable holding your final joined object)

Avoid: bpy.ops.object.shade_naked() [doesn't exist], ShaderNodeTexClouds [doesn't exist, use ShaderNodeTexNoise], numpy or random imports, hardcoded file paths, GLTF_SEPARATE export format.

Output the Think Block and Phase 2 Code as two clearly separated blocks so I can copy them individually.

===== USER REQUEST =====
Category: ${categoryName}
Prompt: ${promptText}`;
}

// ─── Fixed sections reference content ───────────────────────────────
const FIXED_IMPORTS_REF = `import bpy
import bmesh
import math
import os
from mathutils import Vector`;

const FIXED_PHASE1_REF = `# ==============================================================================
# Phase 1: Setup and Clean Scene
# ==============================================================================
bpy.ops.wm.read_factory_settings(use_empty=True)`;

const FIXED_PHASE3_REF = `# ==============================================================================
# Phase 3: Export & Render
# ==============================================================================
light_data = bpy.data.lights.new(name="Light", type='AREA')
light_data.energy = 1000
light_data.size = 5.0
light_obj = bpy.data.objects.new(name="Light", object_data=light_data)
bpy.context.collection.objects.link(light_obj)
light_obj.location = (4, -4, 5)

cam_data = bpy.data.cameras.new("Camera")
cam_obj = bpy.data.objects.new("Camera", cam_data)
bpy.context.collection.objects.link(cam_obj)
bpy.context.scene.camera = cam_obj
cam_obj.location = (0, -6, 3)

tt = cam_obj.constraints.new(type='TRACK_TO')
tt.target = {{OBJECT}}
tt.track_axis = 'TRACK_NEGATIVE_Z'
tt.up_axis = 'UP_Y'
bpy.context.view_layer.update()

cwd = os.getcwd()
bpy.ops.object.select_all(action='DESELECT')
{{OBJECT}}.select_set(True)
bpy.ops.export_scene.gltf(
    filepath=os.path.join(cwd, "model.glb"),
    export_format='GLB',
    use_selection=True,
    export_apply=True
)

try:
    bpy.context.scene.render.engine = 'BLENDER_EEVEE_NEXT'
except TypeError:
    bpy.context.scene.render.engine = 'BLENDER_EEVEE'

bpy.context.scene.render.filepath = os.path.join(cwd, "render.png")
bpy.context.scene.render.resolution_x = 512
bpy.context.scene.render.resolution_y = 512
bpy.context.scene.render.film_transparent = True
bpy.ops.render.render(write_still=True)`;


export default function EntryEditorPage() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [entry, setEntry] = useState(null);
  const [prompt, setPrompt] = useState(null);
  const [categoryName, setCategoryName] = useState('');
  const [thinkBlock, setThinkBlock] = useState('');
  const [phase2Code, setPhase2Code] = useState('');
  const [saving, setSaving] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [withdrawing, setWithdrawing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);
  const [copied, setCopied] = useState(false);

  // Test-run state
  const [running, setRunning] = useState(false);
  const [latestJob, setLatestJob] = useState(null);
  const [viewMode, setViewMode] = useState('3d'); // '3d' or 'render'
  const [workersOnline, setWorkersOnline] = useState(0);
  const [isPromptOpen, setIsPromptOpen] = useState(true);
  const [isTerminalOpen, setIsTerminalOpen] = useState(true);
  const [terminalCopied, setTerminalCopied] = useState(false);
  const [promoting, setPromoting] = useState(false);
  const pollRef = useRef(null);
  const modelViewerRef = useRef(null);

  // Build token-bearing URLs for the proxy endpoints
  const token = localStorage.getItem('access_token');
  const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  // If we have a completed test-run job with temp files, show those; otherwise show saved entry files
  const hasTestRunResult = latestJob?.status === 'done' && latestJob?.is_test_run && (latestJob?.temp_glb_url || latestJob?.temp_render_url);
  const testCacheBuster = latestJob?.completed_at ? `&t=${new Date(latestJob.completed_at).getTime()}` : '';
  const entryCacheBuster = entry?.updated_at ? `&t=${new Date(entry.updated_at).getTime()}` : '';

  const modelUrl = hasTestRunResult && latestJob?.temp_glb_url
    ? `${baseUrl}/api/entries/${id}/jobs/${latestJob.id}/temp-model?token=${token}${testCacheBuster}`
    : (entry?.glb_url ? `${baseUrl}/api/entries/${id}/model?token=${token}${entryCacheBuster}` : null);
  const renderUrl = hasTestRunResult && latestJob?.temp_render_url
    ? `${baseUrl}/api/entries/${id}/jobs/${latestJob.id}/temp-render?token=${token}${testCacheBuster}`
    : (entry?.render_url ? `${baseUrl}/api/entries/${id}/render?token=${token}${entryCacheBuster}` : null);

  useEffect(() => {
    fetchEntry();
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [id]);

  async function fetchEntry() {
    setLoading(true);
    try {
      const res = await api.get('/api/entries', { params: {} });
      const found = res.data.find((e) => e.id === id);
      if (!found) { setError('Entry not found'); setLoading(false); return; }
      setEntry(found);
      setThinkBlock(found.think_block || '');
      setPhase2Code(found.phase2_code || '');

      try {
        const promptRes = await api.get(`/api/prompts/${found.prompt_id}`);
        setPrompt(promptRes.data);

        // Fetch category name from taxonomy
        try {
          const taxRes = await api.get('/api/taxonomy/phases');
          for (const phase of taxRes.data) {
            for (const sub of (phase.subphases || [])) {
              for (const cat of (sub.categories || [])) {
                if (cat.id === promptRes.data.category_id) {
                  setCategoryName(cat.name);
                }
              }
            }
          }
        } catch { /* taxonomy fetch failed, category stays empty */ }
      } catch { setPrompt(null); }

      // Fetch latest jobs to resume polling if one is still running
      try {
        const jobsRes = await api.get(`/api/entries/${id}/jobs`);
        if (jobsRes.data.length > 0) {
          const recentJob = jobsRes.data[0];
          if (recentJob.status === 'pending' || recentJob.status === 'running') {
            setLatestJob(recentJob);
            startPolling();
          }
        }
      } catch { /* no jobs yet */ }
      
      // Fetch workers health
      try {
        const workersRes = await api.get('/api/workers/health');
        setWorkersOnline(workersRes.data.filter(w => w.status === 'online').length);
      } catch (e) {
        console.error("Failed to fetch workers", e);
      }
      
    } catch (err) {
      setError('Failed to load entry');
    } finally {
      setLoading(false);
    }
  }

  // ─── Copy Instructions ──────────────────────────────────────
  function handleCopyInstructions() {
    const text = buildInstructionsTemplate(
      categoryName || 'unknown',
      prompt?.prompt_text || ''
    );
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  function handleCopyTerminal() {
    let text = '';
    if (latestJob) {
      if (latestJob.status === 'pending') text = 'Waiting for worker to claim job...';
      else if (latestJob.status === 'running') text = 'Blender is executing the script...';
      else if (latestJob.status === 'done') text = latestJob.error_log || '✓ Script executed successfully. No errors.';
      else if (latestJob.status === 'failed') text = latestJob.error_log || 'Job failed — no error log available.';
    } else {
      text = "No execution logs yet. Click 'Run' to test your code.";
    }
    navigator.clipboard.writeText(text).then(() => {
      setTerminalCopied(true);
      setTimeout(() => setTerminalCopied(false), 2000);
    });
  }

  async function handleSave() {
    setSaving(true);
    setSaved(false);
    setError('');
    try {
      let res;
      if (latestJob?.id && latestJob.status === 'done' && latestJob.is_test_run) {
        // Promote the test run (this syncs the DB script to the snapshot that actually generated the model)
        res = await api.post(`/api/entries/${id}/promote-test`, { job_id: latestJob.id });
        setLatestJob(null);
        setThinkBlock(res.data.think_block || '');
        setPhase2Code(res.data.phase2_code || '');
      } else {
        // Normal save
        res = await api.patch(`/api/entries/${id}`, { think_block: thinkBlock, phase2_code: phase2Code });
      }
      setEntry(res.data);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Save failed');
    } finally {
      setSaving(false);
    }
  }

  async function handleSubmit() {
    if (!phase2Code.trim()) { setError('Cannot submit an empty phase 2 script.'); return; }
    setSubmitting(true);
    setError('');
    try {
      if (latestJob?.id && latestJob.status === 'done' && latestJob.is_test_run) {
        // Promote before submitting to ensure model is saved
        await api.post(`/api/entries/${id}/promote-test`, { job_id: latestJob.id });
        setLatestJob(null);
      } else {
        // Normal save before submitting
        await api.patch(`/api/entries/${id}`, { think_block: thinkBlock, phase2_code: phase2Code });
      }
      const res = await api.post(`/api/entries/${id}/submit`);
      setEntry(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Submit failed');
    } finally {
      setSubmitting(false);
    }
  }

  async function handleWithdraw() {
    setWithdrawing(true);
    try {
      const res = await api.post(`/api/entries/${id}/withdraw`);
      setEntry(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Withdraw failed');
    } finally {
      setWithdrawing(false);
    }
  }

  // ─── Test Run ─────────────────────────────────────────────
  async function handleTestRun() {
    if (!phase2Code.trim()) { setError('Cannot run an empty phase 2 script.'); return; }
    
    // Client-side hard block for final_object_name
    const lines = phase2Code.split('\n').filter(l => l.trim() !== '');
    if (lines.length === 0) {
      setError('Phase 2 code is empty.');
      return;
    }
    const lastLine = lines[lines.length - 1];
    if (!/^final_object_name\s*=\s*['"]?[A-Za-z0-9_]+['"]?/.test(lastLine.trim())) {
      setError('Phase 2 code must end with exactly: final_object_name = "YourVariableName" (or without quotes).');
      return;
    }
    
    setRunning(true);
    setError('');
    try {
      const res = await api.post(`/api/entries/${id}/test-run`, { think_block: thinkBlock, phase2_code: phase2Code });
      setLatestJob(res.data);
      startPolling();
    } catch (err) {
      setError(err.response?.data?.detail || 'Test run failed');
      setRunning(false);
    }
  }

  function startPolling() {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const jobsRes = await api.get(`/api/entries/${id}/jobs`);
        if (jobsRes.data.length > 0) {
          const latest = jobsRes.data[0];
          setLatestJob(latest);
          if (latest.status === 'done' || latest.status === 'failed') {
            clearInterval(pollRef.current);
            pollRef.current = null;
            setRunning(false);
            // Refresh entry to get updated render_url / glb_url
            if (latest.status === 'done') {
              const entryRes = await api.get('/api/entries');
              const found = entryRes.data.find((e) => e.id === id);
              if (found) setEntry(found);
            }
          }
        }
      } catch { /* ignore poll errors */ }
    }, POLL_INTERVAL);
  }

  // ─── Viewer controls ─────────────────────────────────────
  function resetCamera() {
    const mv = modelViewerRef.current;
    if (!mv) return;
    mv.cameraOrbit = 'auto auto auto';
    mv.cameraTarget = 'auto auto auto';
    mv.fieldOfView = 'auto';
  }

  function toggleAutoRotate() {
    const mv = modelViewerRef.current;
    if (!mv) return;
    if (mv.hasAttribute('auto-rotate')) {
      mv.removeAttribute('auto-rotate');
    } else {
      mv.setAttribute('auto-rotate', '');
    }
  }

  // Compute the live object name for the reference panel
  const liveObjectName = (() => {
    if (!phase2Code) return '{{OBJECT}}';
    const lines = phase2Code.split('\n').filter(l => l.trim() !== '');
    if (lines.length === 0) return '{{OBJECT}}';
    const last = lines[lines.length - 1].trim();
    const m = last.match(/^final_object_name\s*=\s*['"]?([A-Za-z0-9_]+)['"]?/);
    return m ? m[1] : '{{OBJECT}}';
  })();

  // ─── Render ──────────────────────────────────────────────
  if (loading) {
    return (
      <div className="loading-page" style={{ minHeight: 300 }}>
        <span className="spinner" /> Loading entry...
      </div>
    );
  }

  if (error && !entry) {
    return (
      <div className="empty-state">
        <p>{error}</p>
        <button className="btn btn-outline mt-4" onClick={() => navigate('/entries')}>
          Back to entries
        </button>
      </div>
    );
  }

  const isEditable = ['draft', 'needs_fix'].includes(entry.status);
  const isSubmitted = entry.status === 'submitted';

  const jobStatusColor = {
    pending: 'var(--status-submitted)',
    running: 'var(--accent)',
    done: 'var(--status-approved)',
    failed: 'var(--status-rejected)',
  };

  return (
    <div className="entry-editor-layout">
      {/* ── Header ─────────────────────────────────────────── */}
      <div className="entry-editor-topbar">
        <button className="btn btn-outline btn-sm" onClick={() => navigate('/entries')}>
          &larr; Back
        </button>
        <div className="flex items-center gap-2">
          <span className="entry-code-label">{entry.code || 'No code'}</span>
          <span className={`status-badge status-${entry.status}`}>
            {entry.status.replace('_', ' ')}
          </span>
        </div>
      </div>

      <div className="ee-prompt-header" style={{ maxHeight: isPromptOpen ? '150px' : '44px', overflowY: isPromptOpen ? 'auto' : 'hidden', transition: 'max-height 0.2s' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
            <div 
              className="ee-prompt-label" 
              style={{ cursor: 'pointer', marginBottom: isPromptOpen ? '8px' : '0' }}
              onClick={() => setIsPromptOpen(!isPromptOpen)}
            >
              <MessageSquare size={14} style={{ marginRight: 4 }} /> 
              Prompt {prompt?.code ? `(${prompt.code})` : ''}
              {isPromptOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </div>
            
            {isPromptOpen && (
              <>
                <div className="ee-prompt-text">{prompt?.prompt_text || 'Loading prompt...'}</div>
                {prompt?.tags?.length > 0 && (
                  <div className="ee-prompt-tags">
                    {prompt.tags.map((tag, i) => (
                      <span key={i} className="ee-tag">{tag}</span>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
          {isPromptOpen && (
            <button
              className="btn btn-sm btn-outline"
              onClick={handleCopyInstructions}
              title="Copy AI instructions to clipboard"
              style={{ whiteSpace: 'nowrap', marginLeft: 12, flexShrink: 0 }}
            >
              {copied ? '✓ Copied!' : '📋 Copy Instructions'}
            </button>
          )}
        </div>
      </div>

      <div className="entry-editor-workspace">
        {/* Reviewer notes */}
        {entry.reviewer_notes && entry.status === 'needs_fix' && (
          <div className="ee-reviewer-notes" style={{ margin: '12px 20px' }}>
            <strong>Reviewer Notes:</strong> {entry.reviewer_notes}
          </div>
        )}

        <div className="ee-main-panels">
          {/* ── Editor Panes ── */}
          <div className="ee-editors-container">
            {/* Think Block */}
            <div className="ee-editor-pane">
              <div className="ee-editor-header">
                <span>💭 Think Block</span>
              </div>
              <textarea
                className="ee-script-textarea"
                value={thinkBlock}
                onChange={(e) => setThinkBlock(e.target.value)}
                disabled={!isEditable}
                placeholder={`To create "..." procedurally in Blender, I need...`}
                spellCheck={false}
              />
              {/* Fixed Sections Reference */}
              <details className="ee-reference-panel" style={{ padding: '0 12px 12px', background: 'var(--bg-primary)' }}>
                <summary className="ee-reference-summary">Fixed Sections Reference (Read-only)</summary>
                <div className="ee-reference-body">
                  <div className="ee-reference-section-label">Imports (fixed)</div>
                  <pre className="ee-reference-code">{FIXED_IMPORTS_REF}</pre>

                  <div className="ee-reference-section-label" style={{ marginTop: 12 }}>Phase 1 — Scene Setup (fixed)</div>
                  <pre className="ee-reference-code">{FIXED_PHASE1_REF}</pre>

                  <div className="ee-reference-section-label" style={{ marginTop: 12 }}>
                    Phase 3 — Export &amp; Render (fixed, <code style={{ color: 'var(--accent)' }}>{`{{OBJECT}}`}</code> → <code style={{ color: 'var(--status-approved)' }}>{liveObjectName}</code>)
                  </div>
                  <pre className="ee-reference-code">{FIXED_PHASE3_REF.replaceAll('{{OBJECT}}', liveObjectName)}</pre>
                </div>
              </details>
            </div>

            {/* Phase 2 Code */}
            <div className="ee-editor-pane">
              <div className="ee-editor-header">
                <span>📝 Phase 2 Code</span>
                <div className="flex gap-2 items-center">
                  {isEditable && (
                    <button 
                      className="ee-run-btn"
                      onClick={handleTestRun}
                      disabled={running || withdrawing}
                    >
                      {running ? (
                        <><span className="spinner spinner-sm" style={{ width: 14, height: 14, borderWidth: 2 }} /> Running...</>
                      ) : (
                        <>▶ Run (Test)</>
                      )}
                    </button>
                  )}
                </div>
              </div>
              <textarea
                className="ee-script-textarea"
                value={phase2Code}
                onChange={(e) => setPhase2Code(e.target.value)}
                disabled={!isEditable}
                placeholder={`# Your Phase 2 Blender script here...\n# Ends with an assignment like: final_object_name = "my_chair"`}
                spellCheck={false}
              />
            </div>
          </div>

          {/* ── Right Panel: 3D Viewer ── */}
          <div className="ee-viewer-pane">

            {/* View toggle */}
            <div className="ee-view-toggle">
              <label className={viewMode === '3d' ? 'active' : ''}>
                <input
                  type="radio"
                  name="viewMode"
                  value="3d"
                  checked={viewMode === '3d'}
                  onChange={() => setViewMode('3d')}
                />
                3D View
              </label>
              <label className={viewMode === 'render' ? 'active' : ''}>
                <input
                  type="radio"
                  name="viewMode"
                  value="render"
                  checked={viewMode === 'render'}
                  onChange={() => setViewMode('render')}
                />
                Render
              </label>
            </div>

            {/* Test run result banner */}
            {hasTestRunResult && isEditable && (
              <div style={{
                background: 'rgba(46, 204, 113, 0.15)',
                border: '1px solid var(--status-approved)',
                borderRadius: 8,
                padding: '10px 14px',
                marginBottom: 8,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 8,
              }}>
                <span style={{ fontSize: '0.85rem' }}>
                  🧪 <strong>Test run preview</strong> — click "Save draft" below to keep this result.
                </span>
              </div>
            )}

            <div className="ee-viewer-container">
              {viewMode === '3d' ? (
                modelUrl ? (
                  <model-viewer
                    ref={modelViewerRef}
                    src={modelUrl}
                    alt="Generated 3D Model"
                    auto-rotate
                    camera-controls
                    shadow-intensity="1"
                    interaction-prompt="none"
                    style={{ width: '100%', height: '100%' }}
                  />
                ) : (
                  <div className="ee-viewer-empty">
                    <div className="ee-viewer-empty-icon">📦</div>
                    <p>No 3D model yet</p>
                    <p className="text-muted">Run the script to generate a model</p>
                  </div>
                )
              ) : (
                renderUrl ? (
                  <img
                    src={renderUrl}
                    alt="Render output"
                    className="ee-render-img"
                  />
                ) : (
                  <div className="ee-viewer-empty">
                    <div className="ee-viewer-empty-icon">🖼️</div>
                    <p>No render yet</p>
                    <p className="text-muted">Run the script to generate a render</p>
                  </div>
                )
              )}
            </div>

            {/* Viewer toolbar */}
            {viewMode === '3d' && modelUrl && (
              <div className="ee-viewer-toolbar">
                <button onClick={resetCamera} title="Reset View">🏠 Reset</button>
                <button onClick={toggleAutoRotate} title="Toggle Auto Rotate">🔁 Spin</button>
              </div>
            )}

            {/* File links */}
            {(entry.render_url || entry.glb_url) && (
              <div className="ee-file-links">
                {entry.render_url && (
                  <a href={entry.render_url} target="_blank" rel="noreferrer" className="ee-file-link">
                    📷 Open render in Drive
                  </a>
                )}
                {entry.glb_url && (
                  <a href={entry.glb_url} target="_blank" rel="noreferrer" className="ee-file-link">
                    📦 Open model in Drive
                  </a>
                )}
              </div>
            )}

          </div>
        </div>

        {/* ── Bottom Panel: Terminal Log & Actions ── */}
        <div className="ee-terminal-area" style={{ height: isTerminalOpen ? '250px' : '44px', transition: 'height 0.2s' }}>
          <div className="ee-terminal-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
              <span style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px' }} onClick={() => setIsTerminalOpen(!isTerminalOpen)}>
                <Terminal size={14} /> Terminal
                {isTerminalOpen ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
              </span>
              {isTerminalOpen && (
                <button 
                  className="btn btn-sm btn-outline" 
                  onClick={handleCopyTerminal} 
                  title="Copy terminal logs"
                  style={{ padding: '2px 8px', fontSize: '0.7rem', height: '24px', minHeight: '24px' }}
                >
                  <Copy size={12} style={{ marginRight: 4 }} /> 
                  {terminalCopied ? 'Copied' : 'Copy'}
                </button>
              )}
            </div>
            <div className="ee-bottom-actions">
              {isEditable && (
                <>
                  <span style={{ fontSize: '0.75rem', color: workersOnline > 0 ? 'var(--status-approved)' : 'var(--text-muted)' }}>
                    {workersOnline > 0 ? `🟢 ${workersOnline} worker(s) online` : '⚪ No workers online'}
                  </span>
                  <button className="btn btn-outline btn-sm" onClick={handleSave} disabled={saving}>
                    {saving ? <span className="spinner spinner-sm" /> : saved ? '✓ Saved!' : 'Save draft'}
                  </button>
                  <button className="btn btn-primary btn-sm" onClick={handleSubmit} disabled={submitting}>
                    {submitting ? <span className="spinner spinner-sm" /> : 'Submit for review'}
                  </button>
                </>
              )}
              {isSubmitted && (
                <button className="btn btn-outline btn-sm" onClick={handleWithdraw} disabled={withdrawing}>
                  {withdrawing ? <span className="spinner spinner-sm" /> : 'Withdraw'}
                </button>
              )}
            </div>
          </div>
          
          {isTerminalOpen && (
            <div className="ee-terminal-content">
              {latestJob ? (
                <div className="ee-log-output">
                  {latestJob.status === 'pending' && 'Waiting for worker to claim job...'}
                  {latestJob.status === 'running' && 'Blender is executing the script...'}
                  {latestJob.status === 'done' && (latestJob.error_log || '✓ Script executed successfully. No errors.')}
                  {latestJob.status === 'failed' && (latestJob.error_log || 'Job failed — no error log available.')}
                </div>
              ) : (
                <div className="ee-log-output" style={{ color: 'var(--text-muted)' }}>
                  No execution logs yet. Click 'Run' to test your code.
                </div>
              )}
            </div>
          )}
        </div>
      </div>

    </div>
  );
}
