import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Loader2, Home, ChevronDown, ChevronRight, FileCode, FolderTree } from 'lucide-react';
import WikiTreeView from '../components/WikiTreeView';
import MarkdownRenderer from '../components/MarkdownRenderer';
import FileTreeView from '../components/FileTreeView';
import ChatPanel from '../components/ChatPanel';
import { getAnalysis, analyzeRepository } from '../api/client';
import { SECTIONS } from '../types';

export default function WikiPage() {
  const { repoUrl } = useParams();
  const decodedUrl = repoUrl ? decodeURIComponent(repoUrl) : '';
  const navigate = useNavigate();

  const [analysis, setAnalysis] = useState(null);
  const [activeSection, setActiveSection] = useState('purpose_scope');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showRelevantFiles, setShowRelevantFiles] = useState(false);
  const [showFileTree, setShowFileTree] = useState(false);

  useEffect(() => {
    if (!decodedUrl) return;

    const fetchAnalysis = async () => {
      setLoading(true);
      setError(null);

      try {
        let data = await getAnalysis(decodedUrl);

        if (!data) {
          data = await analyzeRepository(decodedUrl);
        }

        setAnalysis(data);
        console.log('[CodeLens] Analysis data:', {
          sections: Object.keys(data).filter(k => !k.startsWith('_')),
          globalFiles: data._relevant_files?.length || 0,
          commitHash: data._commit_hash,
          perSectionFiles: Object.keys(data).filter(k => k.startsWith('_relevant_files_')),
        });
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load analysis');
      } finally {
        setLoading(false);
      }
    };

    fetchAnalysis();
  }, [decodedUrl]);

  const handleRefresh = async () => {
    if (!decodedUrl) return;

    setLoading(true);
    setError(null);

    try {
      const data = await analyzeRepository(decodedUrl, true);
      setAnalysis(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to refresh analysis');
    } finally {
      setLoading(false);
    }
  };

  const getActiveContent = () => {
    if (!analysis) return '';
    return analysis[activeSection] || '';
  };

  const getSectionLabel = () => {
    const section = SECTIONS.find((s) => s.id === activeSection);
    return section?.label || activeSection;
  };

  const getRelevantFiles = () => {
    if (!analysis) return [];
    // Try per-section files first, fall back to global
    const sectionKey = `_relevant_files_${activeSection}`;
    return analysis[sectionKey] || analysis._relevant_files || [];
  };

  const getCommitHash = () => {
    if (!analysis) return '';
    return analysis._commit_hash || '';
  };

  const getFileTree = () => {
    if (!analysis) return {};
    return analysis._file_tree || {};
  };

  const getGitHubBaseUrl = () => {
    const repoName = decodedUrl.replace('https://github.com/', '');
    const commitHash = getCommitHash();
    if (commitHash) {
      return `https://github.com/${repoName}/blob/${commitHash}`;
    }
    return `https://github.com/${repoName}`;
  };

  const repoName = decodedUrl.replace('https://github.com/', '');

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
        <div className="text-center">
          <div className="relative">
            <div className="w-16 h-16 border-4 border-emerald-500/20 border-t-emerald-500 rounded-full animate-spin mx-auto mb-6"></div>
          </div>
          <p className="text-slate-200 text-lg font-medium">Analyzing repository...</p>
          <p className="text-slate-400 text-sm mt-2">{repoName}</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
        <div className="text-center max-w-md">
          <div className="w-16 h-16 bg-red-500/10 rounded-full flex items-center justify-center mx-auto mb-4">
            <span className="text-red-400 text-2xl">!</span>
          </div>
          <p className="text-slate-200 mb-4">{error}</p>
          <button
            onClick={() => navigate('/')}
            className="text-emerald-400 hover:text-emerald-300 inline-flex items-center gap-2 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Try another repository
          </button>
        </div>
      </div>
    );
  }

  const relevantFiles = getRelevantFiles();
  const fileTree = getFileTree();

  return (
    <div className="flex h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      <WikiTreeView activeSection={activeSection} onSectionChange={setActiveSection} repoName={repoName} />

      <div className="flex-1 flex flex-col overflow-hidden">
        <main className="flex-1 overflow-y-auto pb-24">
          <div className="max-w-4xl mx-auto px-8 py-10">
            <div className="mb-8">
              <div className="flex items-center gap-2 text-slate-400 text-sm mb-3">
                <button onClick={() => navigate('/')} className="hover:text-slate-200 transition-colors">
                  <Home className="w-4 h-4" />
                </button>
                <span>/</span>
                <span className="text-slate-300">{repoName}</span>
                <span>/</span>
                <span className="text-emerald-400">{getSectionLabel()}</span>
              </div>
              <h1 className="text-3xl font-bold text-white">{getSectionLabel()}</h1>
            </div>

            {/* Relevant source files collapsible */}
            {relevantFiles.length > 0 && (
              <div className="mb-6 bg-slate-800/50 rounded-2xl border border-slate-700/50 overflow-hidden">
                <button
                  onClick={() => setShowRelevantFiles(!showRelevantFiles)}
                  className="w-full px-6 py-4 flex items-center justify-between text-left hover:bg-slate-700/30 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <FileCode className="w-5 h-5 text-emerald-400" />
                    <span className="font-medium text-white">Relevant source files</span>
                    <span className="text-xs text-slate-400 bg-slate-700/50 px-2 py-0.5 rounded-full">
                      {relevantFiles.length}
                    </span>
                  </div>
                  {showRelevantFiles ? (
                    <ChevronDown className="w-5 h-5 text-slate-400" />
                  ) : (
                    <ChevronRight className="w-5 h-5 text-slate-400" />
                  )}
                </button>
                {showRelevantFiles && (
                  <div className="px-6 pb-4 border-t border-slate-700/50">
                    <div className="mt-3 max-h-64 overflow-y-auto space-y-1">
                      {relevantFiles.map((file, idx) => (
                        <a
                          key={`${file.path}-${idx}`}
                          href={`${getGitHubBaseUrl()}/${file.path}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-2 px-3 py-1.5 rounded-lg hover:bg-slate-700/50 transition-colors group"
                        >
                          <FileCode className="w-4 h-4 text-slate-500 group-hover:text-emerald-400 transition-colors" />
                          <span className="text-sm text-slate-300 group-hover:text-white transition-colors font-mono">
                            {file.path}
                          </span>
                          {file.language && (
                            <span className="text-xs text-slate-500 bg-slate-700/50 px-1.5 py-0.5 rounded">
                              {file.language}
                            </span>
                          )}
                          {file.relevance_score && (
                            <span className="text-xs text-emerald-500/70 ml-auto">
                              {(file.relevance_score * 100).toFixed(0)}%
                            </span>
                          )}
                        </a>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* File Tree collapsible */}
            {Object.keys(fileTree).length > 0 && (
              <div className="mb-6 bg-slate-800/50 rounded-2xl border border-slate-700/50 overflow-hidden">
                <button
                  onClick={() => setShowFileTree(!showFileTree)}
                  className="w-full px-6 py-4 flex items-center justify-between text-left hover:bg-slate-700/30 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <FolderTree className="w-5 h-5 text-emerald-400" />
                    <span className="font-medium text-white">File structure</span>
                  </div>
                  {showFileTree ? (
                    <ChevronDown className="w-5 h-5 text-slate-400" />
                  ) : (
                    <ChevronRight className="w-5 h-5 text-slate-400" />
                  )}
                </button>
                {showFileTree && (
                  <div className="px-6 pb-4 border-t border-slate-700/50">
                    <div className="mt-3 max-h-96 overflow-y-auto">
                      <FileTreeView fileTree={fileTree} />
                    </div>
                  </div>
                )}
              </div>
            )}

            <div className="bg-slate-800/50 rounded-2xl border border-slate-700/50 p-8">
              <MarkdownRenderer content={getActiveContent()} />
            </div>
          </div>
        </main>
      </div>

      <ChatPanel repoUrl={decodedUrl} />
    </div>
  );
}
