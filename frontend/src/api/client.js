const API_BASE = import.meta.env.VITE_API_URL || 'https://codelens-g9ft.onrender.com';

const analysisCache = new Map();

// localStorage helpers for recent repos
const RECENT_KEY = 'codelens_recent_repos';
const MAX_RECENT = 20;

function getRecentRepos() {
  try {
    const data = localStorage.getItem(RECENT_KEY);
    return data ? JSON.parse(data) : [];
  } catch {
    return [];
  }
}

function saveRecentRepo(repoUrl, data) {
  try {
    const recent = getRecentRepos();
    const repoName = repoUrl.replace('https://github.com/', '');
    const description = data?.purpose_scope?.split('\n')[0]?.slice(0, 120) || '';
    
    // Remove if already exists
    const filtered = recent.filter(r => r.url !== repoUrl);
    
    // Add to front
    filtered.unshift({
      url: repoUrl,
      name: repoName,
      description,
      timestamp: Date.now(),
      commitHash: data?._commit_hash || '',
    });
    
    // Keep only last 20
    localStorage.setItem(RECENT_KEY, JSON.stringify(filtered.slice(0, MAX_RECENT)));
  } catch (e) {
    console.warn('[CodeLens] Failed to save recent repo:', e);
  }
}

export function getRecentReposList() {
  return getRecentRepos();
}

export function removeRecentRepo(repoUrl) {
  try {
    const recent = getRecentRepos();
    localStorage.setItem(RECENT_KEY, JSON.stringify(recent.filter(r => r.url !== repoUrl)));
  } catch {}
}

export async function analyzeRepository(repoUrl, forceRefresh = false) {
  const cacheKey = `${repoUrl}:${forceRefresh}`;
  if (!forceRefresh && analysisCache.has(cacheKey)) {
    return analysisCache.get(cacheKey);
  }

  const response = await fetch(`${API_BASE}/api/analysis`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ repo_url: repoUrl, force_refresh: forceRefresh }),
  });

  if (!response.ok) {
    throw new Error('Failed to analyze repository');
  }

  const data = await response.json();
  analysisCache.set(cacheKey, data);
  
  // Save to recent repos
  saveRecentRepo(repoUrl, data);
  
  console.log('[CodeLens] Analysis response:', {
    repoUrl,
    sections: Object.keys(data).filter(k => !k.startsWith('_')),
    relevantFiles: data._relevant_files,
    commitHash: data._commit_hash,
  });
  return data;
}

export async function getAnalysis(repoUrl) {
  const cacheKey = `${repoUrl}:false`;
  if (analysisCache.has(cacheKey)) {
    return analysisCache.get(cacheKey);
  }

  const response = await fetch(`${API_BASE}/api/analysis/${encodeURIComponent(repoUrl)}`);

  if (!response.ok) {
    return null;
  }

  const data = await response.json();
  analysisCache.set(cacheKey, data);
  return data;
}

export async function chat(repoUrl, question) {
  const response = await fetch(`${API_BASE}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ repo_url: repoUrl, question }),
  });

  if (!response.ok) {
    throw new Error('Failed to get response');
  }

  const data = await response.json();
  return data.answer;
}
