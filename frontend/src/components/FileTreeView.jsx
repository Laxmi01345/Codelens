import { useState } from 'react';
import { Folder, FolderOpen, FileText, ChevronRight, ChevronDown } from 'lucide-react';

function FileNode({ name, data, path = '', level = 0 }) {
  const [isOpen, setIsOpen] = useState(level < 2);
  const isDir = data.type !== 'file' || data.children;
  const fullPath = path ? `${path}/${name}` : name;

  if (isDir) {
    const children = data.children || data;
    const entries = typeof children === 'object' && !Array.isArray(children)
      ? Object.entries(children).filter(([k]) => k !== 'type' && k !== 'size')
      : [];

    return (
      <div>
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="flex items-center gap-1.5 py-0.5 hover:bg-slate-700/30 rounded px-1 w-full text-left group"
          style={{ paddingLeft: `${level * 16}px` }}
        >
          {isOpen ? (
            <ChevronDown className="w-3.5 h-3.5 text-slate-500 shrink-0" />
          ) : (
            <ChevronRight className="w-3.5 h-3.5 text-slate-500 shrink-0" />
          )}
          {isOpen ? (
            <FolderOpen className="w-4 h-4 text-emerald-400 shrink-0" />
          ) : (
            <Folder className="w-4 h-4 text-emerald-400 shrink-0" />
          )}
          <span className="text-sm text-slate-300 group-hover:text-white truncate">{name}</span>
        </button>
        {isOpen && (
          <div>
            {entries.sort(([a], [b]) => {
              const aIsDir = typeof children[a] === 'object' && !children[a]?.type;
              const bIsDir = typeof children[b] === 'object' && !children[b]?.type;
              if (aIsDir && !bIsDir) return -1;
              if (!aIsDir && bIsDir) return 1;
              return a.localeCompare(b);
            }).map(([key, val]) => (
              <FileNode
                key={key}
                name={key}
                data={val}
                path={fullPath}
                level={level + 1}
              />
            ))}
          </div>
        )}
      </div>
    );
  }

  const ext = name.split('.').pop()?.toLowerCase();
  const size = data.size || 0;
  const sizeStr = size < 1024 ? `${size}B` : `${Math.round(size / 1024)}KB`;

  return (
    <div
      className="flex items-center gap-1.5 py-0.5 px-1 hover:bg-slate-700/30 rounded group"
      style={{ paddingLeft: `${level * 16 + 18}px` }}
    >
      <FileText className="w-4 h-4 text-slate-500 shrink-0" />
      <span className="text-sm text-slate-400 group-hover:text-slate-200 truncate">{name}</span>
      <span className="text-xs text-slate-600 ml-auto shrink-0">{sizeStr}</span>
    </div>
  );
}

export default function FileTreeView({ fileTree }) {
  if (!fileTree || Object.keys(fileTree).length === 0) {
    return (
      <div className="text-sm text-slate-500 italic py-4">
        No file tree data available
      </div>
    );
  }

  const rootEntries = Object.entries(fileTree).filter(([k]) => k !== 'type' && k !== 'size');

  return (
    <div className="font-mono text-sm">
      {rootEntries.sort(([a], [b]) => {
        const aIsDir = typeof fileTree[a] === 'object' && !fileTree[a]?.type;
        const bIsDir = typeof fileTree[b] === 'object' && !fileTree[b]?.type;
        if (aIsDir && !bIsDir) return -1;
        if (!aIsDir && bIsDir) return 1;
        return a.localeCompare(b);
      }).map(([name, data]) => (
        <FileNode key={name} name={name} data={data} />
      ))}
    </div>
  );
}
