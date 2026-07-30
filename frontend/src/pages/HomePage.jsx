import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, BookOpen, Layers, Network, Plus, Clock, Trash2 } from 'lucide-react';
import { getRecentReposList, removeRecentRepo } from '../api/client';

function timeAgo(timestamp) {
  const seconds = Math.floor((Date.now() - timestamp) / 1000);
  if (seconds < 60) return 'just now';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export default function HomePage() {
  const [repoUrl, setRepoUrl] = useState('');
  const [recentRepos, setRecentRepos] = useState([]);
  const inputRef = useRef(null);
  const navigate = useNavigate();

  useEffect(() => {
    setRecentRepos(getRecentReposList());
  }, []);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (repoUrl.trim()) {
      const encoded = encodeURIComponent(repoUrl.trim());
      navigate(`/wiki/${encoded}`);
    }
  };

  const handleAddRepo = () => {
    inputRef.current?.focus();
  };

  const handleRemoveRecent = (e, url) => {
    e.stopPropagation();
    removeRecentRepo(url);
    setRecentRepos(getRecentReposList());
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      <div className="flex flex-col items-center justify-center min-h-[calc(100vh-3.5rem)] px-4">
        <div className="max-w-3xl w-full text-center">
          <div className="flex items-center justify-center gap-3 mb-6">
            <div className="w-14 h-14 bg-emerald-500/10 rounded-2xl flex items-center justify-center border border-emerald-500/20">
              <BookOpen className="w-7 h-7 text-emerald-400" />
            </div>
          </div>

          <h1 className="text-5xl font-bold text-white mb-4">
            Code<span className="text-emerald-400">Lens</span>
          </h1>

          <p className="text-lg text-slate-400 mb-10 max-w-xl mx-auto">
            AI-powered repository documentation. Enter a GitHub URL to explore
            codebases with intelligent analysis and interactive diagrams.
          </p>

          <form onSubmit={handleSubmit} className="relative max-w-2xl mx-auto">
            <div className="flex gap-3">
              <div className="relative flex-1">
                <svg className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-500" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
                </svg>
                <input
                  ref={inputRef}
                  type="text"
                  value={repoUrl}
                  onChange={(e) => setRepoUrl(e.target.value)}
                  placeholder="https://github.com/owner/repo"
                  className="w-full pl-12 pr-4 py-4 bg-slate-800/50 border border-slate-700 rounded-xl text-white placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500 transition-all"
                />
              </div>
              <button
                type="submit"
                disabled={!repoUrl.trim()}
                className="px-6 py-4 bg-emerald-500 text-white rounded-xl hover:bg-emerald-600 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center gap-2 font-medium"
              >
                <Search className="w-5 h-5" />
                <span className="hidden sm:inline">Analyze</span>
              </button>
            </div>
          </form>

          <div className="mt-14">
            <h2 className="text-lg font-medium text-slate-300 mb-6 text-center">Which repo would you like to understand?</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              <button
                onClick={handleAddRepo}
                className="p-5 bg-slate-800/40 rounded-2xl border border-dashed border-slate-600 hover:border-emerald-500/50 transition-all text-left group flex flex-col justify-between min-h-[120px]"
              >
                <div>
                  <div className="w-8 h-8 bg-emerald-500/10 rounded-lg flex items-center justify-center mb-3 group-hover:bg-emerald-500/20 transition-colors">
                    <Plus className="w-4 h-4 text-emerald-400" />
                  </div>
                  <span className="font-medium text-white group-hover:text-emerald-400 transition-colors">Add repo</span>
                  <p className="text-xs text-slate-500 mt-1">Paste a GitHub URL above</p>
                </div>
              </button>

              {recentRepos.map((r) => (
                <button
                  key={r.url}
                  onClick={() => navigate(`/wiki/${encodeURIComponent(r.url)}`)}
                  className="p-5 bg-slate-800/40 rounded-2xl border border-slate-700/50 hover:border-emerald-500/40 transition-all text-left group relative min-h-[120px] flex flex-col justify-between"
                >
                  <button
                    onClick={(e) => handleRemoveRecent(e, r.url)}
                    className="absolute top-3 right-3 p-1 opacity-0 group-hover:opacity-100 hover:bg-slate-700/50 rounded transition-all"
                    title="Remove"
                  >
                    <Trash2 className="w-3.5 h-3.5 text-slate-500 hover:text-red-400" />
                  </button>
                  <div>
                    <div className="font-semibold text-white group-hover:text-emerald-400 transition-colors truncate pr-6">
                      {r.name}
                    </div>
                    {r.description && (
                      <div className="text-sm text-slate-400 mt-1 line-clamp-2">{r.description}</div>
                    )}
                  </div>
                  <div className="flex items-center gap-1 text-xs text-slate-500 mt-2">
                    <Clock className="w-3 h-3" />
                    {timeAgo(r.timestamp)}
                  </div>
                </button>
              ))}
            </div>
          </div>

          <div className="mt-16 grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="p-6 bg-slate-800/30 rounded-2xl border border-slate-700/50 hover:border-emerald-500/30 transition-all group">
              <div className="w-12 h-12 bg-emerald-500/10 rounded-xl flex items-center justify-center mb-4 group-hover:bg-emerald-500/20 transition-colors">
                <Layers className="w-6 h-6 text-emerald-400" />
              </div>
              <h3 className="font-semibold text-white mb-2">Deep Analysis</h3>
              <p className="text-sm text-slate-400">
                Understand purpose, architecture, and tech stack with AI-powered insights.
              </p>
            </div>

            <div className="p-6 bg-slate-800/30 rounded-2xl border border-slate-700/50 hover:border-emerald-500/30 transition-all group">
              <div className="w-12 h-12 bg-emerald-500/10 rounded-xl flex items-center justify-center mb-4 group-hover:bg-emerald-500/20 transition-colors">
                <Network className="w-6 h-6 text-emerald-400" />
              </div>
              <h3 className="font-semibold text-white mb-2">Interactive Diagrams</h3>
              <p className="text-sm text-slate-400">
                Visualize code structure with Mermaid class, sequence, and flow diagrams.
              </p>
            </div>

            <div className="p-6 bg-slate-800/30 rounded-2xl border border-slate-700/50 hover:border-emerald-500/30 transition-all group">
              <div className="w-12 h-12 bg-emerald-500/10 rounded-xl flex items-center justify-center mb-4 group-hover:bg-emerald-500/20 transition-colors">
                <BookOpen className="w-6 h-6 text-emerald-400" />
              </div>
              <h3 className="font-semibold text-white mb-2">Wiki-Style Docs</h3>
              <p className="text-sm text-slate-400">
                Browse documentation like DeepWiki with hierarchical navigation.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
