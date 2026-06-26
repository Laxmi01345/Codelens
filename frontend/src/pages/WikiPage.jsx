import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Loader2, Home } from 'lucide-react';
import WikiTreeView from '../components/WikiTreeView';
import MarkdownRenderer from '../components/MarkdownRenderer';
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
