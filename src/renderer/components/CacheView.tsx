import React, { useState, useEffect } from 'react';
import { Database, Trash2, RefreshCw, CheckCircle2, AlertCircle } from 'lucide-react';

interface CacheItem {
    name: string;
    repo_url: string;
    chunk_count: number;
}

interface CacheViewProps {
    onChat?: (repoUrl: string) => void;
}

export const CacheView: React.FC<CacheViewProps> = ({ onChat }) => {
    const [caches, setCaches] = useState<CacheItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [clearing, setClearing] = useState<string | null>(null);

    useEffect(() => {
        fetchCaches();

        // Listen for cache list updates
        const handleCachesList = (payload: any) => {
            setCaches(payload.caches || []);
            setLoading(false);
        };

        const handleCacheCleared = () => {
            setClearing(null);
            // List already refreshed by backend sending caches_list
        };

        window.electronAPI.onMessage((_event, message) => {
            if (message.type === 'caches_list') {
                handleCachesList(message.payload);
            } else if (message.type === 'cache_cleared') {
                handleCacheCleared();
            }
        });

        return () => {
            // Cleanup listener if needed (not strictly required here as it's a global listener)
        };
    }, []);

    const fetchCaches = () => {
        setLoading(true);
        window.electronAPI.sendCommand({ type: 'list_caches', data: {} });
    };

    const handleClearCache = (repoUrl: string) => {
        if (window.confirm(`Are you sure you want to clear the cache for ${repoUrl}? This will delete all code embeddings and cached documentation.`)) {
            setClearing(repoUrl);
            window.electronAPI.sendCommand({ type: 'clear_cache', data: { repoUrl } });
        }
    };

    return (
        <div className="p-6 h-full flex flex-col space-y-6 overflow-auto custom-scrollbar">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold text-white flex items-center gap-2">
                        <Database className="text-primary w-6 h-6" />
                        Cache Management
                    </h2>
                    <p className="text-slate-400 mt-1">Manage local vector embeddings and cached documentation</p>
                </div>
                <button
                    onClick={fetchCaches}
                    className="p-2 text-slate-400 hover:text-white hover:bg-white/5 rounded-full transition-all"
                    title="Refresh List"
                >
                    <RefreshCw className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} />
                </button>
            </div>

            <div className="grid grid-cols-1 gap-4">
                {loading && caches.length === 0 ? (
                    <div className="col-span-1 py-20 flex flex-col items-center justify-center text-slate-500">
                        <RefreshCw className="w-10 h-10 animate-spin mb-4" />
                        <p>Loading cache data...</p>
                    </div>
                ) : caches.length === 0 ? (
                    <div className="col-span-1 py-20 flex flex-col items-center justify-center text-slate-500 border border-dashed border-white/10 rounded-xl">
                        <Database className="w-12 h-12 mb-4 opacity-20" />
                        <p className="text-lg">No caches found</p>
                        <p className="text-sm mt-2">Cached data will appear after your first repository analysis.</p>
                    </div>
                ) : (
                    caches.map((cache) => (
                        <div
                            key={cache.repo_url}
                            className="bg-slate-900/40 border border-white/10 rounded-xl p-5 flex items-center justify-between hover:border-primary/30 transition-all group"
                        >
                            <div className="flex items-center gap-4">
                                <div className="w-12 h-12 bg-primary/10 rounded-lg flex items-center justify-center group-hover:bg-primary/20 transition-all">
                                    <Database className="text-primary w-6 h-6" />
                                </div>
                                <div>
                                    <h3 className="text-white font-medium truncate max-w-md">{cache.repo_url}</h3>
                                    <div className="flex items-center gap-3 mt-1">
                                        <span className="text-xs px-2 py-0.5 bg-slate-800 text-slate-300 rounded-full flex items-center gap-1">
                                            <RefreshCw className="w-3 h-3" />
                                            {cache.chunk_count} Code Chunks
                                        </span>
                                        <span className="text-xs px-2 py-0.5 bg-emerald-500/10 text-emerald-400 rounded-full flex items-center gap-1">
                                            <CheckCircle2 className="w-3 h-3" />
                                            Cached
                                        </span>
                                    </div>
                                </div>
                            </div>

                            <div className="flex items-center gap-2">
                                {onChat && (
                                    <button
                                        onClick={() => onChat(cache.repo_url)}
                                        className="px-3 py-2 bg-blue-600/20 text-blue-400 hover:bg-blue-600/30 rounded-lg text-sm font-medium transition-colors"
                                    >
                                        Chat with Code
                                    </button>
                                )}
                                <button
                                    onClick={() => handleClearCache(cache.repo_url)}
                                    disabled={clearing === cache.repo_url}
                                    className={`p-2 rounded-lg transition-all ${clearing === cache.repo_url
                                        ? 'bg-slate-800 text-slate-500 cursor-not-allowed'
                                        : 'text-red-400 hover:bg-red-500/10 hover:text-red-300'
                                        }`}
                                    title="Clear Cache"
                                >
                                    <Trash2 className={`w-5 h-5 ${clearing === cache.repo_url ? 'animate-pulse' : ''}`} />
                                </button>
                            </div>
                        </div>
                    ))
                )}
            </div>

            {caches.length > 0 && (
                <div className="bg-primary/5 border border-primary/20 rounded-xl p-4 flex gap-4 items-start">
                    <AlertCircle className="text-primary w-6 h-6 shrink-0 mt-0.5" />
                    <div className="text-sm">
                        <h4 className="text-primary font-medium">About Caching</h4>
                        <p className="text-slate-400 mt-1 leading-relaxed">
                            DocAgent uses local vector embeddings (via ChromaDB) to power semantic code search and incremental updates.
                            Caching allows the tool to skip re-analyzing unchanged files, saving API tokens and significantly speeding up repeated analyses.
                        </p>
                    </div>
                </div>
            )}
        </div>
    );
};


