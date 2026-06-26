import {
  Target,
  FolderTree,
  FileCode,
  Layers,
  Network,
} from 'lucide-react';
import { SECTIONS } from '../types';

const ICONS = {
  target: Target,
  'folder-tree': FolderTree,
  'file-code': FileCode,
  layers: Layers,
  network: Network,
};

export default function WikiTreeView({ activeSection, onSectionChange, repoName }) {
  return (
    <nav className="w-64 h-full bg-slate-900/80 border-r border-slate-700/50 overflow-y-auto flex flex-col">
      <div className="p-5 border-b border-slate-700/50">
        <div className="flex items-center gap-2 mb-1">
          <div className="w-2 h-2 bg-emerald-400 rounded-full"></div>
          <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">Documentation</span>
        </div>
        {repoName && (
          <p className="text-sm text-slate-300 truncate mt-2">{repoName}</p>
        )}
      </div>

      <div className="flex-1 p-3">
        <div className="space-y-1">
          {SECTIONS.map((section) => {
            const isActive = activeSection === section.id;
            const IconComponent = ICONS[section.icon];

            return (
              <button
                key={section.id}
                onClick={() => onSectionChange(section.id)}
                className={`
                  w-full flex items-center gap-3 px-3 py-2.5 text-sm rounded-lg transition-all duration-200
                  ${isActive
                    ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 border border-transparent'
                  }
                `}
              >
                {IconComponent && (
                  <IconComponent className={`w-4 h-4 ${isActive ? 'text-emerald-400' : 'text-slate-500'}`} />
                )}
                <span className="truncate">{section.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      <div className="p-4 border-t border-slate-700/50">
        <div className="text-xs text-slate-500 text-center">
          Powered by CodeLens
        </div>
      </div>
    </nav>
  );
}
