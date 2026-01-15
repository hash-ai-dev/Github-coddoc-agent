import React from 'react';
import { Github, Folder, ExternalLink } from 'lucide-react';

interface ReposViewProps {
    repos?: any[];
}

export const ReposView: React.FC<ReposViewProps> = ({ repos = [] }) => {
    if (repos.length === 0) {
        return (
            <div className="flex-1 glass-panel m-1 p-8 flex flex-col items-center justify-center text-slate-500">
                <div className="w-20 h-20 bg-slate-800 rounded-full flex items-center justify-center mb-6">
                    <Folder className="w-10 h-10 text-slate-400" />
                </div>
                <h2 className="text-xl font-semibold text-slate-300 mb-2">No Repositories Synced</h2>
                <p className="max-w-md text-center">
                    Repositories you analyze will appear here for quick access and documentation history.
                </p>
            </div>
        );
    }

    return (
        <div className="flex-1 glass-panel m-1 p-6 overflow-auto">
            <h2 className="text-xl font-semibold text-white mb-4">Synced Repositories</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {repos.map((repo, idx) => (
                    <div key={idx} className="bg-slate-900/50 border border-white/5 rounded-lg p-4 hover:border-primary/50 transition-colors group relative">
                        <div className="flex items-start justify-between mb-2">
                            <div className="p-2 bg-slate-800 rounded text-primary">
                                <Github className="w-5 h-5" />
                            </div>
                            <span className={`text-xs px-2 py-1 rounded-full ${repo.status === 'Documented' ? 'bg-green-500/20 text-green-400' :
                                repo.status === 'Failed' ? 'bg-red-500/20 text-red-400' : 'bg-yellow-500/20 text-yellow-400'}`}>
                                {repo.status}
                            </span>
                        </div>
                        <div className="font-medium text-slate-200 truncate mb-1">{repo.url.replace('https://github.com/', '')}</div>
                        <div className="text-xs text-slate-500 mb-3">Last updated: {repo.last_updated}</div>

                        {repo.confluence_url && (
                            <button
                                onClick={() => window.electronAPI.openExternal(repo.confluence_url)}
                                className="text-xs text-primary hover:text-primary/80 flex items-center gap-1 mt-2 border-t border-white/5 pt-2 w-full"
                            >
                                <ExternalLink className="w-3 h-3" /> View Documentation
                            </button>
                        )}
                    </div>
                ))}
            </div>
        </div>
    );
};
