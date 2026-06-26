import { useEffect, useRef, useState } from 'react';
import mermaid from 'mermaid';
import { ZoomIn, ZoomOut, RotateCcw, Maximize2, X } from 'lucide-react';

let mermaidInitialized = false;
if (!mermaidInitialized) {
  mermaid.initialize({
    startOnLoad: false,
    theme: 'dark',
    securityLevel: 'loose',
    themeVariables: {
      primaryColor: '#10b981',
      primaryTextColor: '#f8fafc',
      primaryBorderColor: '#059669',
      lineColor: '#64748b',
      secondaryColor: '#1e293b',
      tertiaryColor: '#0f172a',
      background: '#1e293b',
      mainBkg: '#1e293b',
      nodeBorder: '#334155',
      clusterBkg: '#1e293b',
      clusterBorder: '#334155',
      titleColor: '#f8fafc',
      edgeLabelBackground: '#1e293b',
      edgeLabelColor: '#94a3b8',
    },
  });
  mermaidInitialized = true;
}

let mermaidIdCounter = 0;

export default function MermaidDiagram({ code, className = '' }) {
  const containerRef = useRef(null);
  const modalRef = useRef(null);
  const [svg, setSvg] = useState('');
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [modalZoom, setModalZoom] = useState(1);
  const [modalPan, setModalPan] = useState({ x: 0, y: 0 });
  const [modalDragging, setModalDragging] = useState(false);
  const [modalDragStart, setModalDragStart] = useState({ x: 0, y: 0 });

  useEffect(() => {
    if (!code || !code.trim()) {
      setError('No diagram code provided');
      setIsLoading(false);
      return;
    }

    let cancelled = false;

    const renderDiagram = async () => {
      setIsLoading(true);
      setError(null);
      setSvg('');

      try {
        let cleanCode = code.trim();
        cleanCode = cleanCode.replace(/^```mermaid\s*/i, '');
        cleanCode = cleanCode.replace(/\s*```$/i, '');
        cleanCode = cleanCode.trim();

        if (!cleanCode) {
          setError('Empty diagram code');
          setIsLoading(false);
          return;
        }

        mermaidIdCounter++;
        const id = `mermaid-diagram-${mermaidIdCounter}`;

        const result = await mermaid.render(id, cleanCode);

        if (!cancelled) {
          setSvg(result.svg);
          setError(null);
        }
      } catch (err) {
        console.error('Mermaid render error:', err);
        if (!cancelled) {
          setError(`Diagram error: ${err.message || 'Invalid diagram syntax'}`);
          setSvg('');
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    renderDiagram();

    return () => {
      cancelled = true;
    };
  }, [code]);

  // Inline zoom controls
  const handleZoomIn = () => setZoom((prev) => Math.min(prev + 0.25, 3));
  const handleZoomOut = () => setZoom((prev) => Math.max(prev - 0.25, 0.25));
  const handleReset = () => { setZoom(1); setPan({ x: 0, y: 0 }); };
  const handleWheel = (e) => {
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault();
      const delta = e.deltaY > 0 ? -0.1 : 0.1;
      setZoom((prev) => Math.max(0.25, Math.min(3, prev + delta)));
    }
  };
  const handleMouseDown = (e) => {
    if (e.button === 0) { setIsDragging(true); setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y }); }
  };
  const handleMouseMove = (e) => {
    if (isDragging) { setPan({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y }); }
  };
  const handleMouseUp = () => setIsDragging(false);

  // Modal zoom controls
  const handleModalZoomIn = () => setModalZoom((prev) => Math.min(prev + 0.25, 3));
  const handleModalZoomOut = () => setModalZoom((prev) => Math.max(prev - 0.25, 0.25));
  const handleModalReset = () => { setModalZoom(1); setModalPan({ x: 0, y: 0 }); };
  const handleModalWheel = (e) => {
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault();
      const delta = e.deltaY > 0 ? -0.1 : 0.1;
      setModalZoom((prev) => Math.max(0.25, Math.min(3, prev + delta)));
    }
  };
  const handleModalMouseDown = (e) => {
    if (e.button === 0) { setModalDragging(true); setModalDragStart({ x: e.clientX - modalPan.x, y: e.clientY - modalPan.y }); }
  };
  const handleModalMouseMove = (e) => {
    if (modalDragging) { setModalPan({ x: e.clientX - modalDragStart.x, y: e.clientY - modalDragStart.y }); }
  };
  const handleModalMouseUp = () => setModalDragging(false);

  useEffect(() => {
    const handleEsc = (e) => {
      if (e.key === 'Escape' && isFullscreen) setIsFullscreen(false);
    };
    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, [isFullscreen]);

  if (error) {
    return (
      <div className={`p-4 bg-red-500/10 rounded-xl border border-red-500/20 ${className}`}>
        <p className="text-sm text-red-400 font-medium">{error}</p>
        <pre className="mt-2 text-xs text-red-300/70 overflow-x-auto whitespace-pre-wrap">{code}</pre>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className={`p-4 bg-slate-800/50 rounded-xl border border-slate-700/50 ${className}`}>
        <div className="text-slate-400 text-sm">Loading diagram...</div>
      </div>
    );
  }

  if (!svg) {
    return (
      <div className={`p-4 bg-slate-800/50 rounded-xl border border-slate-700/50 ${className}`}>
        <p className="text-sm text-slate-400">No diagram to display</p>
      </div>
    );
  }

  const DiagramContent = ({ zoomLevel, panOffset, isModal = false }) => (
    <div
      ref={isModal ? modalRef : containerRef}
      className={`overflow-auto ${isModal ? 'cursor-grab h-[80vh]' : 'cursor-grab'}`}
      style={!isModal ? { minHeight: '300px', maxHeight: '600px' } : undefined}
      onWheel={isModal ? handleModalWheel : handleWheel}
      onMouseDown={isModal ? handleModalMouseDown : handleMouseDown}
      onMouseMove={isModal ? handleModalMouseMove : handleMouseMove}
      onMouseUp={isModal ? handleModalMouseUp : handleMouseUp}
      onMouseLeave={isModal ? handleModalMouseUp : handleMouseUp}
    >
      <div
        className="flex items-center justify-center min-h-full p-4"
        style={{
          transform: `translate(${panOffset.x}px, ${panOffset.y}px) scale(${zoomLevel})`,
          transformOrigin: 'center center',
          transition: (isModal ? modalDragging : isDragging) ? 'none' : 'transform 0.2s ease-out',
        }}
        dangerouslySetInnerHTML={{ __html: svg }}
      />
    </div>
  );

  return (
    <>
      {/* Inline Diagram */}
      <div
        className={`relative bg-slate-800/50 rounded-xl border border-slate-700/50 overflow-hidden group cursor-pointer ${className}`}
        onClick={() => setIsFullscreen(true)}
      >
        {/* Zoom Controls */}
        <div className="absolute top-3 right-3 z-10 flex items-center gap-1 bg-slate-900/80 backdrop-blur-sm rounded-lg p-1 border border-slate-700/50 opacity-0 group-hover:opacity-100 transition-opacity">
          <button onClick={(e) => { e.stopPropagation(); handleZoomIn(); }} className="p-1.5 hover:bg-slate-700/50 rounded-md transition-colors" title="Zoom In">
            <ZoomIn className="w-4 h-4 text-slate-300" />
          </button>
          <button onClick={(e) => { e.stopPropagation(); handleZoomOut(); }} className="p-1.5 hover:bg-slate-700/50 rounded-md transition-colors" title="Zoom Out">
            <ZoomOut className="w-4 h-4 text-slate-300" />
          </button>
          <button onClick={(e) => { e.stopPropagation(); handleReset(); }} className="p-1.5 hover:bg-slate-700/50 rounded-md transition-colors" title="Reset">
            <RotateCcw className="w-4 h-4 text-slate-300" />
          </button>
          <div className="w-px h-4 bg-slate-700/50" />
          <button onClick={(e) => { e.stopPropagation(); setIsFullscreen(true); }} className="p-1.5 hover:bg-slate-700/50 rounded-md transition-colors" title="View Fullscreen">
            <Maximize2 className="w-4 h-4 text-slate-300" />
          </button>
        </div>

        {/* Zoom Level */}
        <div className="absolute top-3 left-3 z-10 px-2 py-1 bg-slate-900/80 backdrop-blur-sm rounded-md border border-slate-700/50 opacity-0 group-hover:opacity-100 transition-opacity">
          <span className="text-xs text-slate-400">{Math.round(zoom * 100)}%</span>
        </div>

        <DiagramContent zoomLevel={zoom} panOffset={pan} />

        {/* Click hint */}
        <div className="absolute bottom-3 left-1/2 -translate-x-1/2 z-10 px-3 py-1.5 bg-slate-900/80 backdrop-blur-sm rounded-full border border-slate-700/50 opacity-0 group-hover:opacity-100 transition-opacity">
          <span className="text-xs text-slate-400">Click to view full screen</span>
        </div>
      </div>

      {/* Fullscreen Modal */}
      {isFullscreen && (
        <div className="fixed inset-0 z-50 flex flex-col">
          {/* Blurred Background */}
          <div
            className="absolute inset-0 bg-slate-900/80 backdrop-blur-md"
            onClick={() => setIsFullscreen(false)}
          />

          {/* Modal Content */}
          <div className="relative z-10 flex flex-col h-full">
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 bg-slate-900/90 border-b border-slate-700/50">
              <div className="flex items-center gap-4">
                <span className="text-sm text-slate-400">Diagram Viewer</span>
                <div className="flex items-center gap-1 bg-slate-800/50 rounded-lg p-1 border border-slate-700/50">
                  <button onClick={handleModalZoomIn} className="p-1.5 hover:bg-slate-700/50 rounded-md transition-colors" title="Zoom In">
                    <ZoomIn className="w-4 h-4 text-slate-300" />
                  </button>
                  <button onClick={handleModalZoomOut} className="p-1.5 hover:bg-slate-700/50 rounded-md transition-colors" title="Zoom Out">
                    <ZoomOut className="w-4 h-4 text-slate-300" />
                  </button>
                  <button onClick={handleModalReset} className="p-1.5 hover:bg-slate-700/50 rounded-md transition-colors" title="Reset">
                    <RotateCcw className="w-4 h-4 text-slate-300" />
                  </button>
                </div>
                <span className="text-xs text-slate-500">{Math.round(modalZoom * 100)}%</span>
              </div>
              <button
                onClick={() => setIsFullscreen(false)}
                className="p-2 hover:bg-slate-700/50 rounded-lg transition-colors"
              >
                <X className="w-5 h-5 text-slate-400" />
              </button>
            </div>

            {/* Diagram */}
            <div className="flex-1 overflow-hidden bg-slate-900/50">
              <DiagramContent zoomLevel={modalZoom} panOffset={modalPan} isModal={true} />
            </div>

            {/* Footer hint */}
            <div className="px-6 py-3 bg-slate-900/90 border-t border-slate-700/50 text-center">
              <span className="text-xs text-slate-500">Ctrl + Scroll to zoom • Drag to pan • Esc to close</span>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
