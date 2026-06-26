const API_BASE = import.meta.env.VITE_API_URL || 'https://codelens-g9ft.onrender.com';

const analysisCache = new Map();

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
