import { useState, useEffect } from 'react';
import api from '../api';

export default function PromptsPage() {
  const [prompts, setPrompts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);

  // Form state
  const [phaseId, setPhaseId] = useState('');
  const [subphaseId, setSubphaseId] = useState('');
  const [categoryId, setCategoryId] = useState('');
  const [promptText, setPromptText] = useState('');
  const [tags, setTags] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  
  // Duplicate handling state
  const [duplicateWarning, setDuplicateWarning] = useState(null);

  useEffect(() => {
    fetchData();
  }, []);

  async function fetchData() {
    setLoading(true);
    try {
      const [promptsRes, taxonomyRes] = await Promise.all([
        api.get('/api/prompts'),
        api.get('/api/taxonomy/phases')
      ]);
      setPrompts(promptsRes.data);
      
      setCategories(taxonomyRes.data);
      
    } catch (err) {
      console.error('Failed to load data', err);
    } finally {
      setLoading(false);
    }
  }

  async function handleSubmit(e, forceCreate = false) {
    if (e) e.preventDefault();
    setError('');
    setSubmitting(true);
    setDuplicateWarning(null);
    
    try {
      const tagsArray = tags.split(',').map(t => t.trim()).filter(Boolean);
      await api.post('/api/prompts', {
        category_id: categoryId,
        prompt_text: promptText,
        tags: tagsArray,
        force_create: forceCreate
      });
      
      setPromptText('');
      setTags('');
      fetchData();
    } catch (err) {
      if (err.response?.status === 409 && err.response?.data?.detail?.duplicates_found) {
        setDuplicateWarning(err.response.data.detail);
      } else {
        setError(err.response?.data?.detail || 'Failed to create prompt');
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div>
      <div className="page-header">
        <h1>Prompts Management</h1>
        <p>Create and view dataset prompts</p>
      </div>

      <div className="card mb-4" style={{ marginBottom: 24 }}>
        <h2 style={{ fontSize: '1.1rem', marginBottom: 16 }}>Create New Prompt</h2>
        {error && <div className="login-error mb-2">{error}</div>}
        
        {duplicateWarning && (
          <div className="reviewer-notes" style={{ marginBottom: 16 }}>
            <strong>Warning: Fuzzy Duplicates Found</strong>
            <p className="mb-2">We found existing prompts that are very similar to yours:</p>
            <ul style={{ paddingLeft: 20, marginBottom: 12, fontSize: '0.85rem' }}>
              {duplicateWarning.similar_prompts.map((p, i) => <li key={i}>{p}</li>)}
            </ul>
            <div className="flex gap-2 mt-2">
              <button 
                className="btn btn-primary btn-sm"
                onClick={() => handleSubmit(null, true)}
                disabled={submitting}
              >
                Create anyway (override)
              </button>
              <button 
                className="btn btn-outline btn-sm"
                onClick={() => setDuplicateWarning(null)}
                disabled={submitting}
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        <form onSubmit={(e) => handleSubmit(e, false)} style={{ display: duplicateWarning ? 'none' : 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="form-group">
            <label>Phase</label>
            <select 
              className="form-input" 
              value={phaseId} 
              onChange={e => { setPhaseId(e.target.value); setSubphaseId(''); setCategoryId(''); }}
              required
            >
              <option value="">Select a phase...</option>
              {categories.map(p => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label>Subphase</label>
            <select 
              className="form-input" 
              value={subphaseId} 
              onChange={e => { setSubphaseId(e.target.value); setCategoryId(''); }}
              required
              disabled={!phaseId}
            >
              <option value="">Select a subphase...</option>
              {categories.find(p => p.id === phaseId)?.subphases?.map(s => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label>Category</label>
            <select 
              className="form-input" 
              value={categoryId} 
              onChange={e => setCategoryId(e.target.value)}
              required
              disabled={!subphaseId}
            >
              <option value="">Select a category...</option>
              {categories.find(p => p.id === phaseId)?.subphases?.find(s => s.id === subphaseId)?.categories?.map(c => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </div>
          
          <div className="form-group">
            <label>Prompt Text</label>
            <textarea 
              className="form-input" 
              value={promptText}
              onChange={e => setPromptText(e.target.value)}
              required
              style={{ minHeight: 80 }}
            />
          </div>

          <div className="form-group">
            <label>Tags (comma separated)</label>
            <input 
              type="text"
              className="form-input"
              value={tags}
              onChange={e => setTags(e.target.value)}
              placeholder="e.g. brick, red, exterior"
            />
          </div>

          <div>
            <button type="submit" className="btn btn-primary" disabled={submitting}>
              {submitting ? <span className="spinner"/> : 'Create Prompt'}
            </button>
          </div>
        </form>
      </div>

      <h2 style={{ fontSize: '1.1rem', marginBottom: 16 }}>All Prompts ({prompts.length})</h2>
      {loading ? (
        <span className="spinner" />
      ) : (
        <div className="entry-list">
          {prompts.map(p => (
            <div key={p.id} className="card">
              <div className="flex justify-between items-center mb-2">
                <span className="text-muted" style={{ fontSize: '0.75rem', fontWeight: 600 }}>{p.code}</span>
              </div>
              <p style={{ fontSize: '0.95rem' }}>{p.prompt_text}</p>
              {p.tags?.length > 0 && (
                <div className="mt-2 flex gap-2">
                  {p.tags.map(t => (
                    <span key={t} style={{ fontSize: '0.7rem', background: 'var(--bg-input)', padding: '2px 8px', borderRadius: 12 }}>
                      {t}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
