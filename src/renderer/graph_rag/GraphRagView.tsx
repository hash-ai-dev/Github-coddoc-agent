import { useState, useEffect } from 'react';
import { ConfigPanel } from './ConfigPanel';
import { GraphRagChat } from './GraphRagChat';
import { RepoIngestionForm } from './RepoIngestionForm';
import { Network, FileSearch, ShieldCheck } from 'lucide-react';

const STORAGE_KEY = 'graphrag_state';

interface GraphRagViewProps {
    messages: { role: string; content: string }[];
    setMessages: React.Dispatch<React.SetStateAction<{ role: string; content: string }[]>>;
}

export function GraphRagView({ messages, setMessages }: GraphRagViewProps) {
    // Load persisted state (connection only, not messages)
    const loadPersistedState = () => {
        try {
            const saved = localStorage.getItem(STORAGE_KEY);
            if (saved) {
                const parsed = JSON.parse(saved);
                // Return connection state but reset messages
                return {
                    viewState: parsed.viewState || 'config',
                    isConnected: parsed.isConnected || false,
                    connectionConfig: parsed.connectionConfig || null
                };
            }
        } catch (e) {
            console.error('Failed to load GraphRAG state:', e);
        }
        return {
            viewState: 'config',
            isConnected: false,
            connectionConfig: null
        };
    };

    const initialState = loadPersistedState();

    const [viewState, setViewState] = useState<'config' | 'chat'>(initialState.viewState);
    const [status, setStatus] = useState('');
    // Messages are now managed by parent App component
    const [isTyping, setIsTyping] = useState(false);
    const [isConnected, setIsConnected] = useState(initialState.isConnected);
    const [showIngestionForm, setShowIngestionForm] = useState(false);
    const [connectionConfig, setConnectionConfig] = useState<any>(initialState.connectionConfig || null);

    // Persist connection state only (not messages - they should reset on restart)
    useEffect(() => {
        try {
            const stateToSave = {
                viewState,
                isConnected,
                connectionConfig
            };
            localStorage.setItem(STORAGE_KEY, JSON.stringify(stateToSave));
        } catch (e) {
            console.error('Failed to save GraphRAG state:', e);
        }
    }, [viewState, isConnected, connectionConfig]);

    // Auto-reconnect on mount if we were previously connected
    useEffect(() => {
        if (isConnected && connectionConfig) {
            console.log('Restoring GraphRAG connection...');
            (window as any).electronAPI.getSettings().then((settings: any) => {
                (window as any).electronAPI.sendCommand({
                    type: 'graphrag_connect',
                    data: { ...connectionConfig, settings }
                });
            });
        }
    }, []);

    // Message listener is now in App.tsx - we just handle typing state here
    useEffect(() => {
        const handleGraphRagMessage = (data: any) => {
            console.log('GraphRAG Message:', data);

            if (data.type === 'response') {
                setIsTyping(false);
            } else if (data.type === 'status') {
                if (data.status === 'connected') {
                    setViewState('chat');
                    setStatus('Connected');
                    setIsConnected(true);
                }
            } else if (data.type === 'progress') {
                setStatus(data.message || 'Processing...');
            }
        };

        if ((window as any).electronAPI?.onGraphRagMessage) {
            const cleanup = (window as any).electronAPI.onGraphRagMessage(handleGraphRagMessage);
            return cleanup;
        }

        return () => { };
    }, []);

    const handleConnect = async (config: any) => {
        setStatus('Connecting...');

        // Save connection config
        setConnectionConfig(config);

        // Get settings for API keys
        const settings = await (window as any).electronAPI.getSettings();

        (window as any).electronAPI.sendCommand({
            type: 'graphrag_connect',
            data: { ...config, settings }
        });
    };

    const handleQuery = (query: string) => {
        setMessages(prev => [...prev, { role: 'user', content: query }]);
        setIsTyping(true);
        (window as any).electronAPI.sendCommand({
            type: 'graphrag_query',
            data: { query }
        });
    };

    const handleIngest = () => {
        if (!isConnected) {
            setMessages(prev => [...prev, {
                role: 'assistant',
                content: "⚠️ **Graph Service not connected.**\n\nPlease follow these steps:\n1. Click the **Config** button above\n2. Enter your Neo4j connection details (URI, username, password)\n3. Click **Connect**\n4. Then try **Ingest Repo** again"
            }]);
            return;
        }
        setShowIngestionForm(true);
    };

    const handleIngestionSubmit = (config: any) => {
        setShowIngestionForm(false);
        setMessages(prev => [...prev, {
            role: 'assistant',
            content: `Starting ingestion for repository: ${config.repoUrl}...`
        }]);

        (window as any).electronAPI.sendCommand({
            type: 'graphrag_ingest_github',
            data: {
                repoUrl: config.repoUrl,
                githubToken: config.githubToken,
                branch: config.branch
            }
        });
    };

    return (
        <div className="h-full flex flex-col gap-4 animate-in fade-in zoom-in-95 duration-300 pb-2">
            <header className="flex items-center justify-between px-2 pb-4 border-b border-white/5 shrink-0">
                <div className="flex items-center gap-3">
                    <div className="p-2 bg-purple-500/20 rounded-lg text-purple-400">
                        <Network className="w-6 h-6" />
                    </div>
                    <div>
                        <h2 className="text-xl font-bold text-slate-100">Code Intelligence</h2>
                        <p className="text-sm text-slate-400">Graph-based business understanding</p>
                    </div>
                </div>

                {viewState === 'chat' && (
                    <div className="flex gap-2">
                        <button
                            onClick={() => setViewState('config')}
                            className="px-3 py-1.5 text-xs font-medium text-slate-400 hover:text-white bg-white/5 hover:bg-white/10 rounded-lg transition-colors"
                        >
                            Config
                        </button>
                        <button
                            onClick={() => {
                                if (confirm('⚠️ This will delete ALL data from Neo4j. Are you sure?')) {
                                    (window as any).electronAPI.sendCommand({
                                        type: 'graphrag_clear'
                                    });
                                }
                            }}
                            className="px-3 py-1.5 text-xs font-medium text-red-400 hover:text-white bg-red-500/10 hover:bg-red-500/20 rounded-lg transition-colors"
                        >
                            Clear Data
                        </button>
                        <button
                            onClick={handleIngest}
                            className="px-3 py-1.5 text-xs font-medium text-white bg-primary hover:bg-primary/90 rounded-lg transition-colors flex items-center gap-2"
                        >
                            <FileSearch className="w-3 h-3" />
                            Ingest Repo
                        </button>
                    </div>
                )}
            </header>

            <div className="flex-1 min-h-0 relative overflow-hidden">
                {viewState === 'config' ? (
                    <ConfigPanel onConnect={handleConnect} status={status} />
                ) : (
                    <GraphRagChat
                        messages={messages}
                        onQuery={handleQuery}
                        isTyping={isTyping}
                    />
                )}
            </div>

            {/* Disclaimer Footer */}
            <div className="flex items-center gap-2 text-[10px] text-slate-600 justify-center py-2 shrink-0">
                <ShieldCheck className="w-3 h-3" />
                <span>Isolated Environment • Read-Only Access • No Code Mutations</span>
            </div>

            {/* Ingestion Form Modal */}
            {showIngestionForm && (
                <RepoIngestionForm
                    onSubmit={handleIngestionSubmit}
                    onCancel={() => setShowIngestionForm(false)}
                />
            )}
        </div>
    );
}
