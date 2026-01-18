import { useState, useEffect, Suspense, lazy } from 'react';

import { DashboardView } from './components/DashboardView';
import { SettingsView } from './components/SettingsView';
import { ReposView } from './components/ReposView';
import { DocumentationEditor } from './components/DocumentationEditor';
import { CacheView } from './components/CacheView';
import { Book, Settings, Github, LayoutDashboard, Database, Minus, Square, X, Bot, MessageSquare, Network } from 'lucide-react';
import { ChatInterface, Message } from './components/ChatInterface';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

const GraphRagView = lazy(() => import('./graph_rag/GraphRagView').then(module => ({ default: module.GraphRagView })));

function cn(...inputs: (string | undefined | null | false)[]) {
    return twMerge(clsx(inputs));
}

function App() {
    const [activeTab, setActiveTab] = useState('dashboard');
    const [repoUrl, setRepoUrl] = useState('');
    const [isAnalyzing, setIsAnalyzing] = useState(false);
    const [progress, setProgress] = useState(0);
    const [statusMsg, setStatusMsg] = useState('Ready');
    const [repos, setRepos] = useState<any[]>([]);
    const [generatedDoc, setGeneratedDoc] = useState<any>(null);

    // Chat State (Lifted for Persistence)
    const [chatMessages, setChatMessages] = useState<Message[]>([
        {
            id: 'welcome',
            role: 'assistant',
            content: "Hello! I'm your code assistant. Ask me anything about this repository, and I'll use the codebase context to answer.",
            timestamp: Date.now()
        }
    ]);

    // GraphRAG Chat State (Session-only persistence)
    const [graphRagMessages, setGraphRagMessages] = useState<{ role: string; content: string }[]>([
        {
            role: 'assistant',
            content: "Welcome to Code Intelligence. I can explain your codebase in plain business language using GraphRAG. Please connect to Neo4j to begin."
        }
    ]);

    useEffect(() => {
        if (window.electronAPI) {
            // ... existing listeners ...
            window.electronAPI.onSystem((data) => {
                setStatusMsg(data.message);
            });
            window.electronAPI.onProgress((data) => {
                setProgress(data.percent);
            });
            window.electronAPI.onStatus((data) => {
                if (data.message === 'Analysis Complete') {
                    setIsAnalyzing(false);
                }
            });
            // Error handling
            if (window.electronAPI.onError) {
                window.electronAPI.onError((data) => {
                    setIsAnalyzing(false);
                    setStatusMsg('Error');
                    showToast(data.message, 'error');
                });
            }
            // Listen for repo list updates
            if (window.electronAPI.onRepos) {
                window.electronAPI.onRepos((data: { repos: any[] }) => {
                    setRepos(data.repos || []);
                });
            }
            // Listen for documentation complete
            if (window.electronAPI.onDocumentationComplete) {
                window.electronAPI.onDocumentationComplete((data: { message: string; documentation: any }) => {
                    setIsAnalyzing(false);
                    setProgress(100);
                    setStatusMsg('Documentation Ready');
                    setGeneratedDoc(data.documentation);
                });
            }

            // Global Chat Listener
            let cleanupChat: (() => void) | undefined;
            if (window.electronAPI.onChatResponse) {
                cleanupChat = window.electronAPI.onChatResponse((data) => {
                    setChatMessages(prev => {
                        // Prevent duplicate messages
                        if (prev.some(m => m.content === data.answer && Date.now() - m.timestamp < 1000)) {
                            return prev;
                        }
                        return [
                            ...prev,
                            {
                                id: Date.now().toString(),
                                role: 'assistant',
                                content: data.answer,
                                timestamp: Date.now()
                            }
                        ];
                    });
                });
            }

            // GraphRAG Chat Listener
            let cleanupGraphRag: (() => void) | undefined;
            if (window.electronAPI.onGraphRagMessage) {
                cleanupGraphRag = window.electronAPI.onGraphRagMessage((data: any) => {
                    // Check if we've already shown initial sync messages this session
                    const hasShownInitialSync = sessionStorage.getItem('graphrag_initial_sync_shown');

                    if (data.type === 'response') {
                        setGraphRagMessages(prev => [
                            ...prev,
                            { role: 'assistant', content: data.answer || 'No response' }
                        ]);
                    } else if (data.type === 'progress') {
                        // Only show progress messages if we haven't completed initial sync
                        if (!hasShownInitialSync && data.message) {
                            setGraphRagMessages(prev => [
                                ...prev,
                                { role: 'assistant', content: `📊 ${data.message}` }
                            ]);
                        }
                    } else if (data.type === 'status') {
                        if (data.status === 'connected') {
                            // Only show connection message if it's the first time
                            if (!hasShownInitialSync) {
                                setGraphRagMessages(prev => [
                                    ...prev,
                                    { role: 'assistant', content: `**Connected successfully!** ${data.message || ''}\n\nYou can now ask questions or ingest a repository.` }
                                ]);
                            }
                        } else if (data.status === 'ingested') {
                            setGraphRagMessages(prev => [
                                ...prev,
                                { role: 'assistant', content: "**Ingestion Complete.** The knowledge graph is ready." }
                            ]);
                        } else if (data.status === 'synced') {
                            // Mark that initial sync is complete
                            sessionStorage.setItem('graphrag_initial_sync_shown', 'true');

                            // Only show sync complete message on first sync
                            if (!hasShownInitialSync) {
                                setGraphRagMessages(prev => [
                                    ...prev,
                                    { role: 'assistant', content: "✅ All repositories synchronized. Ready to answer questions!" }
                                ]);
                            }
                        }
                    }
                });
            }

            // Initial fetch
            window.electronAPI.sendCommand({ type: 'list_repos', data: {} });

            // Store cleanup to be called on unmount
            return () => {
                if (cleanupChat) cleanupChat();
                if (cleanupGraphRag) cleanupGraphRag();
            };
        }
    }, []);

    const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'info' } | null>(null);

    const showToast = (message: string, type: 'success' | 'error' | 'info' = 'info') => {
        setToast({ message, type });
        setTimeout(() => setToast(null), 5000);
    };

    const handleStartAnalysis = async () => {
        if (!repoUrl) return;

        // Fetch current settings from UI store
        const settings = await window.electronAPI.getSettings();

        setIsAnalyzing(true);
        setStatusMsg('Initializing...');
        setProgress(0);

        window.electronAPI.sendCommand({
            type: 'start_analysis',
            data: {
                repoUrl,
                settings // Pass UI settings to backend
            }
        });
    };

    return (
        <div className="flex h-screen w-screen bg-background text-slate-100 font-sans overflow-hidden">
            {/* Sidebar */}
            <aside className="w-16 md:w-20 flex flex-col items-center py-6 gap-6 glass border-r border-white/5 z-20">
                <div className="p-2 mb-4 text-primary bg-primary/10 rounded-xl">
                    <Book className="w-6 h-6" />
                </div>

                <NavIcon icon={LayoutDashboard} active={activeTab === 'dashboard'} onClick={() => setActiveTab('dashboard')} />
                <NavIcon icon={Github} active={activeTab === 'repos'} onClick={() => setActiveTab('repos')} />
                <NavIcon icon={MessageSquare} active={activeTab === 'chat'} onClick={() => setActiveTab('chat')} />
                <NavIcon icon={Database} active={activeTab === 'cache'} onClick={() => setActiveTab('cache')} />
                <NavIcon icon={Network} active={activeTab === 'graph_rag'} onClick={() => setActiveTab('graph_rag')} />
                <NavIcon icon={Settings} active={activeTab === 'settings'} onClick={() => setActiveTab('settings')} />
            </aside>

            {/* Main Content */}
            <main className="flex-1 flex flex-col h-full relative z-10">
                {/* Header Region (Drag) */}
                <div className="h-8 w-full drag-region select-none flex justify-end items-center px-2 gap-1" style={{ WebkitAppRegion: 'drag' } as any}>
                    <div className="flex items-center gap-1 no-drag" style={{ WebkitAppRegion: 'no-drag' } as any}>
                        <button
                            onClick={() => window.electronAPI.minimize()}
                            className="p-1.5 hover:bg-white/10 text-slate-400 hover:text-white rounded-md transition-colors"
                            title="Minimize"
                        >
                            <Minus className="w-4 h-4" />
                        </button>
                        <button
                            onClick={() => window.electronAPI.maximize()}
                            className="p-1.5 hover:bg-white/10 text-slate-400 hover:text-white rounded-md transition-colors"
                            title="Maximize"
                        >
                            <Square className="w-4 h-4" />
                        </button>
                        <button
                            onClick={() => window.electronAPI.close()}
                            className="p-1.5 hover:bg-red-500/80 text-slate-400 hover:text-white rounded-md transition-colors"
                            title="Close"
                        >
                            <X className="w-4 h-4" />
                        </button>
                    </div>
                </div>

                <div className="flex-1 p-6 flex flex-col gap-6 overflow-hidden">

                    {/* Header */}
                    <header className="flex justify-between items-center px-2">
                        <div>
                            <h1 className="text-2xl font-bold bg-gradient-to-r from-blue-400 to-cyan-400 bg-clip-text text-transparent">
                                DocAgent
                            </h1>
                            <p className="text-slate-400 text-sm flex items-center gap-2">
                                <span className={`w-2 h-2 rounded-full ${statusMsg === 'Ready' || statusMsg.includes('Complete') ? 'bg-green-500' :
                                    statusMsg === 'Error' ? 'bg-red-500' : 'bg-amber-500 animate-pulse'}`}></span>
                                {statusMsg}
                            </p>
                        </div>

                        <div className="glass px-4 py-2 rounded-lg flex items-center gap-2 text-xs text-slate-400">
                            <span>v1.0.0</span>
                        </div>
                    </header>

                    {/* Toast Notification */}
                    {toast && (
                        <div className={`absolute top-20 right-8 z-50 px-4 py-3 rounded-lg shadow-lg border border-white/10 flex items-center gap-3 animate-in fade-in slide-in-from-top-4 ${toast.type === 'error' ? 'bg-red-500/10 text-red-200 border-red-500/20' :
                            toast.type === 'success' ? 'bg-green-500/10 text-green-200 border-green-500/20' :
                                'bg-slate-800 text-slate-200'
                            }`}>
                            {toast.type === 'error' ? <div className="w-2 h-2 rounded-full bg-red-500" /> :
                                toast.type === 'success' ? <div className="w-2 h-2 rounded-full bg-green-500" /> :
                                    <div className="w-2 h-2 rounded-full bg-blue-500" />}
                            <span className="text-sm font-medium">{toast.message}</span>
                        </div>
                    )}

                    {/* Main View Area */}
                    {activeTab === 'dashboard' && (
                        <DashboardView
                            repoUrl={repoUrl}
                            setRepoUrl={setRepoUrl}
                            handleStartAnalysis={handleStartAnalysis}
                            isAnalyzing={isAnalyzing}
                            progress={progress}
                        />
                    )}

                    {activeTab === 'chat' && repoUrl && !isAnalyzing ? (
                        <div className="flex-1 h-full min-h-0">
                            <ChatInterface
                                repoUrl={repoUrl}
                                messages={chatMessages}
                                setMessages={setChatMessages}
                            />
                        </div>
                    ) : activeTab === 'chat' ? (
                        <div className="flex-1 flex flex-col items-center justify-center text-slate-500 gap-4">
                            <Bot className="w-16 h-16 opacity-20" />
                            <h2 className="text-xl font-semibold text-slate-300">Start Chatting</h2>
                            <p className="max-w-xs text-center">Select a repository to start an AI chat session with your codebase context.</p>

                            <div className="flex gap-3 mt-4">
                                <button
                                    onClick={() => setActiveTab('dashboard')}
                                    className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg transition-colors flex items-center gap-2"
                                >
                                    <LayoutDashboard className="w-4 h-4" />
                                    Analyze New
                                </button>
                                <button
                                    onClick={() => setActiveTab('cache')}
                                    className="px-4 py-2 bg-primary hover:bg-primary/90 text-white rounded-lg transition-colors flex items-center gap-2"
                                >
                                    <Database className="w-4 h-4" />
                                    Select from Database
                                </button>
                            </div>
                        </div>
                    ) : null}

                    {activeTab === 'repos' && <ReposView repos={repos} />}

                    {activeTab === 'cache' && (
                        <CacheView
                            onChat={(repoUrl) => {
                                setRepoUrl(repoUrl);
                                setActiveTab('chat');
                            }}
                        />
                    )}

                    {activeTab === 'settings' && <SettingsView />}

                    {activeTab === 'graph_rag' && (
                        <Suspense fallback={<div className="flex items-center justify-center h-full text-slate-500">Loading Intelligence...</div>}>
                            <GraphRagView
                                messages={graphRagMessages}
                                setMessages={setGraphRagMessages}
                            />
                        </Suspense>
                    )}
                </div>
            </main>

            {/* Background Ambience */}
            <div className="absolute top-[-20%] left-[-10%] w-[50%] h-[50%] rounded-full bg-primary/20 blur-[120px] pointer-events-none z-0" />
            <div className="absolute bottom-[-20%] right-[-10%] w-[40%] h-[40%] rounded-full bg-purple-500/10 blur-[100px] pointer-events-none z-0" />

            {/* Documentation Editor Modal */}
            {generatedDoc && (
                <DocumentationEditor
                    documentation={generatedDoc}
                    onClose={() => setGeneratedDoc(null)}
                />
            )}
        </div>
    );
}

function NavIcon({ icon: Icon, active, onClick }: { icon: any, active: boolean, onClick: () => void }) {
    return (
        <button
            onClick={onClick}
            className={cn(
                "p-3 rounded-xl transition-all duration-300 relative group",
                active ? "text-white bg-white/10 shadow-lg shadow-white/5" : "text-slate-400 hover:text-white hover:bg-white/5"
            )}
        >
            <Icon className="w-6 h-6" />
            {active && <div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-8 bg-primary rounded-r-full -ml-4" />}
        </button>
    );
}

export default App;
