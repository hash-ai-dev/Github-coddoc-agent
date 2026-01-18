import { useState, useEffect } from 'react';
import { Save, Database } from 'lucide-react';

interface ConfigPanelProps {
    onConnect: (config: any) => void;
    status: string;
}

export function ConfigPanel({ onConnect, status }: ConfigPanelProps) {
    const [uri, setUri] = useState('neo4j://localhost:7687');
    const [user, setUser] = useState('neo4j');
    const [password, setPassword] = useState('');

    // Save/Load locally for convenience (not secure, but fine for local tool)
    useEffect(() => {
        const saved = localStorage.getItem('graphrag_config');
        if (saved) {
            const parsed = JSON.parse(saved);
            setUri(parsed.uri || 'neo4j://localhost:7687');
            setUser(parsed.user || 'neo4j');
        }
    }, []);

    const handleConnect = () => {
        localStorage.setItem('graphrag_config', JSON.stringify({ uri, user }));
        onConnect({ neo4jUri: uri, neo4jUser: user, neo4jPassword: password });
    };

    return (
        <div className="glass p-6 rounded-xl flex flex-col gap-4 max-w-md mx-auto mt-10">
            <div className="flex items-center gap-3 text-primary mb-2">
                <Database className="w-6 h-6" />
                <h2 className="text-xl font-semibold">Graph Database Connection</h2>
            </div>

            <div className="space-y-2">
                <label className="text-sm text-slate-400">Neo4j URI</label>
                <input
                    type="text"
                    value={uri}
                    onChange={(e) => setUri(e.target.value)}
                    className="w-full bg-slate-800/50 border border-white/10 rounded-lg px-3 py-2 text-slate-200 outline-none focus:border-primary/50"
                    placeholder="neo4j://localhost:7687"
                />
            </div>

            <div className="space-y-2">
                <label className="text-sm text-slate-400">Username</label>
                <input
                    type="text"
                    value={user}
                    onChange={(e) => setUser(e.target.value)}
                    className="w-full bg-slate-800/50 border border-white/10 rounded-lg px-3 py-2 text-slate-200 outline-none focus:border-primary/50"
                />
            </div>

            <div className="space-y-2">
                <label className="text-sm text-slate-400">Password</label>
                <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full bg-slate-800/50 border border-white/10 rounded-lg px-3 py-2 text-slate-200 outline-none focus:border-primary/50"
                />
            </div>

            <button
                onClick={handleConnect}
                className="mt-4 bg-primary hover:bg-primary/90 text-white font-medium py-2 rounded-lg flex items-center justify-center gap-2 transition-colors"
            >
                <Save className="w-4 h-4" />
                Connect & Initialize
            </button>

            {status && (
                <div className={`mt-2 text-sm text-center ${status.includes('Failed') ? 'text-red-400' : 'text-green-400'}`}>
                    {status}
                </div>
            )}
        </div>
    );
}
