import { useState, useEffect, useMemo } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import api from '../api';

export default function EntryListPage() {
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState('code');
  const [sortDir, setSortDir] = useState('asc');

  // Taxonomy + batch dropdown state
  const [taxonomy, setTaxonomy] = useState([]);       // phases → subphases → categories
  const [prompts, setPrompts] = useState([]);          // all prompts (for prompt_id → category_id mapping)
  const [batches, setBatches] = useState([]);           // all batches
  const [phaseFilter, setPhaseFilter] = useState('');
  const [subphaseFilter, setSubphaseFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [batchFilter, setBatchFilter] = useState('');

  const navigate = useNavigate();

  useEffect(() => {
    fetchAll();
  }, []);

  async function fetchAll() {
    setLoading(true);
    try {
      const [entriesRes, taxRes, promptsRes, batchesRes] = await Promise.all([
        api.get('/api/entries'),
        api.get('/api/taxonomy/phases'),
        api.get('/api/prompts'),
        api.get('/api/batches'),
      ]);
      setEntries(entriesRes.data);
      setTaxonomy(taxRes.data);
      setPrompts(promptsRes.data);
      setBatches(batchesRes.data);
    } catch (err) {
      console.error('Failed to load data', err);
      // Try loading just entries if the other calls fail
      try {
        const res = await api.get('/api/entries');
        setEntries(res.data);
      } catch {}
    } finally {
      setLoading(false);
    }
  }

  // ── Lookup maps ──
  // prompt_id → category_id
  const promptToCategoryMap = useMemo(() => {
    const map = {};
    for (const p of prompts) {
      map[p.id] = p.category_id;
    }
    return map;
  }, [prompts]);

  // category_id → { subphase_id, phase_id }
  const categoryLookup = useMemo(() => {
    const map = {};
    for (const phase of taxonomy) {
      for (const sub of phase.subphases || []) {
        for (const cat of sub.categories || []) {
          map[cat.id] = { subphase_id: sub.id, phase_id: phase.id };
        }
      }
    }
    return map;
  }, [taxonomy]);

  // ── Cascading dropdown options ──
  const subphaseOptions = useMemo(() => {
    if (!phaseFilter) return [];
    const phase = taxonomy.find((p) => p.id === phaseFilter);
    return phase?.subphases || [];
  }, [taxonomy, phaseFilter]);

  const categoryOptions = useMemo(() => {
    if (!subphaseFilter) return [];
    const sub = subphaseOptions.find((s) => s.id === subphaseFilter);
    return sub?.categories || [];
  }, [subphaseOptions, subphaseFilter]);

  // Batches available for the dropdown (all batches the user can see)
  const batchOptions = useMemo(() => {
    // Only show batches that actually have entries in the current dataset
    const batchIdsInEntries = new Set(entries.map((e) => e.batch_id));
    return batches.filter((b) => batchIdsInEntries.has(b.id));
  }, [batches, entries]);

  // Reset child dropdowns when parent changes
  function handlePhaseChange(val) {
    setPhaseFilter(val);
    setSubphaseFilter('');
    setCategoryFilter('');
  }
  function handleSubphaseChange(val) {
    setSubphaseFilter(val);
    setCategoryFilter('');
  }

  // ── Status counts (from ALL entries) ──
  const statusCounts = useMemo(() => {
    const counts = { all: entries.length };
    for (const e of entries) {
      counts[e.status] = (counts[e.status] || 0) + 1;
    }
    return counts;
  }, [entries]);

  // ── Filtered + searched + sorted entries ──
  const filteredEntries = useMemo(() => {
    let result = entries;

    // Status filter
    if (statusFilter !== 'all') {
      result = result.filter((e) => e.status === statusFilter);
    }

    // Batch filter
    if (batchFilter) {
      result = result.filter((e) => e.batch_id === batchFilter);
    }

    // Taxonomy filters (phase → subphase → category)
    if (categoryFilter) {
      // Exact category match
      result = result.filter((e) => {
        const catId = promptToCategoryMap[e.prompt_id];
        return catId === categoryFilter;
      });
    } else if (subphaseFilter) {
      // All categories in this subphase
      const catIds = new Set(categoryOptions.map((c) => c.id));
      // Also include categories from subphase even if categoryOptions hasn't updated
      const sub = subphaseOptions.find((s) => s.id === subphaseFilter);
      if (sub) {
        for (const cat of sub.categories || []) catIds.add(cat.id);
      }
      result = result.filter((e) => {
        const catId = promptToCategoryMap[e.prompt_id];
        return catIds.has(catId);
      });
    } else if (phaseFilter) {
      // All categories in all subphases of this phase
      const catIds = new Set();
      const phase = taxonomy.find((p) => p.id === phaseFilter);
      if (phase) {
        for (const sub of phase.subphases || []) {
          for (const cat of sub.categories || []) {
            catIds.add(cat.id);
          }
        }
      }
      result = result.filter((e) => {
        const catId = promptToCategoryMap[e.prompt_id];
        return catIds.has(catId);
      });
    }

    // Search filter
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      result = result.filter((e) => {
        const code = (e.code || '').toLowerCase();
        const batchId = (e.batch_id || '').toLowerCase();
        return code.includes(q) || batchId.includes(q);
      });
    }

    // Sort
    result = [...result].sort((a, b) => {
      let cmp = 0;
      if (sortBy === 'code') {
        cmp = (a.code || '').localeCompare(b.code || '');
      } else if (sortBy === 'updated') {
        cmp = new Date(a.updated_at) - new Date(b.updated_at);
      } else if (sortBy === 'status') {
        cmp = a.status.localeCompare(b.status);
      }
      return sortDir === 'asc' ? cmp : -cmp;
    });

    return result;
  }, [entries, statusFilter, batchFilter, phaseFilter, subphaseFilter, categoryFilter, searchQuery, sortBy, sortDir, promptToCategoryMap, taxonomy, categoryOptions, subphaseOptions]);

  function toggleSort(field) {
    if (sortBy === field) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortBy(field);
      setSortDir('asc');
    }
  }

  const sortIcon = (field) => {
    if (sortBy !== field) return '↕';
    return sortDir === 'asc' ? '↑' : '↓';
  };

  // Batch name lookup
  const batchNameMap = useMemo(() => {
    const map = {};
    for (const b of batches) map[b.id] = b.name;
    return map;
  }, [batches]);

  const statuses = ['all', 'draft', 'needs_fix', 'submitted', 'approved', 'rejected'];
  const statusEmoji = {
    all: '📋',
    draft: '📝',
    needs_fix: '🔧',
    submitted: '📤',
    approved: '✅',
    rejected: '❌',
  };

  const hasAnyDropdownFilter = phaseFilter || subphaseFilter || categoryFilter || batchFilter;

  function clearAllFilters() {
    setStatusFilter('all');
    setSearchQuery('');
    setPhaseFilter('');
    setSubphaseFilter('');
    setCategoryFilter('');
    setBatchFilter('');
  }

  return (
    <div>
      <div className="page-header">
        <h1>My Entries</h1>
        <p>Your assigned prompts and their current status</p>
      </div>

      {/* ── Filter Bar ── */}
      <div className="el-filter-bar">
        {/* Status pills */}
        <div className="el-status-pills">
          {statuses.map((s) => (
            <button
              key={s}
              className={`el-pill ${statusFilter === s ? 'el-pill-active' : ''}`}
              onClick={() => setStatusFilter(s)}
            >
              <span className="el-pill-emoji">{statusEmoji[s]}</span>
              <span className="el-pill-label">{s === 'all' ? 'All' : s.replace('_', ' ')}</span>
              {(statusCounts[s] || 0) > 0 && (
                <span className="el-pill-count">{statusCounts[s]}</span>
              )}
            </button>
          ))}
        </div>

        {/* Taxonomy + Batch dropdowns */}
        <div className="el-dropdowns">
          <select
            className="el-dropdown"
            value={phaseFilter}
            onChange={(e) => handlePhaseChange(e.target.value)}
          >
            <option value="">All Phases</option>
            {taxonomy.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>

          <select
            className="el-dropdown"
            value={subphaseFilter}
            onChange={(e) => handleSubphaseChange(e.target.value)}
            disabled={!phaseFilter}
          >
            <option value="">All Subphases</option>
            {subphaseOptions.map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>

          <select
            className="el-dropdown"
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            disabled={!subphaseFilter}
          >
            <option value="">All Categories</option>
            {categoryOptions.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>

          <select
            className="el-dropdown"
            value={batchFilter}
            onChange={(e) => setBatchFilter(e.target.value)}
          >
            <option value="">All Batches</option>
            {batchOptions.map((b) => (
              <option key={b.id} value={b.id}>{b.name}</option>
            ))}
          </select>

          {hasAnyDropdownFilter && (
            <button className="el-clear-btn" onClick={clearAllFilters} title="Clear all filters">
              ✕ Clear
            </button>
          )}
        </div>

        {/* Search + Sort */}
        <div className="el-controls">
          <div className="el-search-box">
            <span className="el-search-icon">🔍</span>
            <input
              type="text"
              placeholder="Search by code..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="el-search-input"
            />
            {searchQuery && (
              <button className="el-search-clear" onClick={() => setSearchQuery('')}>
                ✕
              </button>
            )}
          </div>

          <div className="el-sort-btns">
            <button
              className={`el-sort-btn ${sortBy === 'code' ? 'el-sort-active' : ''}`}
              onClick={() => toggleSort('code')}
              title="Sort by code"
            >
              Code {sortIcon('code')}
            </button>
            <button
              className={`el-sort-btn ${sortBy === 'updated' ? 'el-sort-active' : ''}`}
              onClick={() => toggleSort('updated')}
              title="Sort by last updated"
            >
              Updated {sortIcon('updated')}
            </button>
            <button
              className={`el-sort-btn ${sortBy === 'status' ? 'el-sort-active' : ''}`}
              onClick={() => toggleSort('status')}
              title="Sort by status"
            >
              Status {sortIcon('status')}
            </button>
          </div>
        </div>
      </div>

      {/* ── Results summary ── */}
      {!loading && (
        <div className="el-results-summary">
          Showing <strong>{filteredEntries.length}</strong> of{' '}
          <strong>{entries.length}</strong> entries
          {statusFilter !== 'all' && (
            <span>
              {' '}
              · filtered by <span className={`status-badge status-${statusFilter}`}>{statusFilter.replace('_', ' ')}</span>
            </span>
          )}
          {batchFilter && batchNameMap[batchFilter] && (
            <span> · batch: {batchNameMap[batchFilter]}</span>
          )}
          {searchQuery && (
            <span> · matching "{searchQuery}"</span>
          )}
        </div>
      )}

      {/* ── Entry List ── */}
      {loading ? (
        <div className="loading-page" style={{ minHeight: 200 }}>
          <span className="spinner" />
        </div>
      ) : filteredEntries.length === 0 ? (
        <div className="empty-state">
          <p>
            No entries found
            {statusFilter !== 'all' ? ` with status "${statusFilter}"` : ''}
            {searchQuery ? ` matching "${searchQuery}"` : ''}.
          </p>
          <p className="text-muted mt-1">
            {entries.length === 0
              ? 'Entries appear here once a Lead assigns prompts to you.'
              : 'Try adjusting your filters.'}
          </p>
        </div>
      ) : (
        <div className="entry-list">
          {filteredEntries.map((entry) => (
            <Link
              to={`/entries/${entry.id}`}
              key={entry.id}
              className="entry-card"
              style={{ textDecoration: 'none', color: 'inherit' }}
            >
              <div className="entry-card-left">
                <span className="entry-prompt">
                  {entry.code || `Entry ${entry.id.substring(0, 8)}`}
                </span>
                <span className="entry-meta">
                  Updated {new Date(entry.updated_at).toLocaleDateString()} &middot;{' '}
                  {batchNameMap[entry.batch_id] || `Batch ${entry.batch_id.substring(0, 8)}`}
                </span>
              </div>
              <div className="entry-card-right">
                <span className={`status-badge status-${entry.status}`}>
                  {entry.status.replace('_', ' ')}
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
