import { useState } from 'react';
import { X, Github, Key, GitBranch, Cpu } from 'lucide-react';

interface RepoIngestionFormProps {
    onSubmit: (config: {
        repoUrl: string;
        githubToken: string;
        branch: string;
        hfApiKey: string;
        modelName: string;
    }) => void;
    onCancel: () => void;
}

export function RepoIngestionForm({ onSubmit, onCancel }: RepoIngestionFormProps) {
    // Initialize state from localStorage with explicit callbacks
    const [repoUrl, setRepoUrl] = useState(() => {
        const saved = localStorage.getItem('graphrag_last_repo_url') || '';
        console.log('Loading repo URL from localStorage:', saved);
        return saved;
    });
    const [githubToken, setGithubToken] = useState(() => localStorage.getItem('graphrag_github_token') || '');
    const [branch, setBranch] = useState(() => localStorage.getItem('graphrag_last_branch') || 'main');
    const [hfApiKey, setHfApiKey] = useState(() => localStorage.getItem('graphrag_hf_key') || '');
    const [modelName, setModelName] = useState(() => localStorage.getItem('graphrag_model_name') || 'Qwen/Qwen2.5-Coder-7B-Instruct');

    // Migrate old model name to new one
    useState(() => {
        const currentModel = localStorage.getItem('graphrag_model_name');
        // Migrate any old models to the new Qwen Coder model
        if (currentModel && !currentModel.includes('Qwen2.5-Coder-7B')) {
            console.log('Migrating to Qwen2.5-Coder-7B-Instruct for better code understanding');
            localStorage.setItem('graphrag_model_name', 'Qwen/Qwen2.5-Coder-7B-Instruct');
            setModelName('Qwen/Qwen2.5-Coder-7B-Instruct');
        }
    });

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();

        // Save all values to localStorage for next time
        if (githubToken) localStorage.setItem('graphrag_github_token', githubToken);
        if (repoUrl) localStorage.setItem('graphrag_last_repo_url', repoUrl);
        if (branch) localStorage.setItem('graphrag_last_branch', branch);
        if (modelName) localStorage.setItem('graphrag_model_name', modelName);
        if (hfApiKey) localStorage.setItem('graphrag_hf_key', hfApiKey);

        onSubmit({
            repoUrl,
            githubToken,
            branch,
            hfApiKey,
            modelName
        });
    };

    return (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 animate-in fade-in duration-200">
            <div className="bg-slate-900 border border-white/10 rounded-2xl p-6 w-full max-w-2xl mx-4 shadow-2xl animate-in zoom-in-95 duration-200">
                <div className="flex items-center justify-between mb-6">
                    <div className="flex items-center gap-3">
                        <div className="p-2 bg-purple-500/20 rounded-lg">
                            <Github className="w-6 h-6 text-purple-400" />
                        </div>
                        <div>
                            <h2 className="text-xl font-bold text-white">Ingest GitHub Repository</h2>
                            <p className="text-sm text-slate-400">Configure repository and credentials</p>
                        </div>
                    </div>
                    <button
                        onClick={onCancel}
                        className="p-2 hover:bg-white/5 rounded-lg transition-colors text-slate-400 hover:text-white"
                    >
                        <X className="w-5 h-5" />
                    </button>
                </div>

                <form onSubmit={handleSubmit} className="space-y-4">
                    {/* Repository URL */}
                    <div>
                        <label className="block text-sm font-medium text-slate-300 mb-2">
                            <Github className="w-4 h-4 inline mr-2" />
                            Repository URL
                        </label>
                        <input
                            type="url"
                            value={repoUrl}
                            onChange={(e) => setRepoUrl(e.target.value)}
                            placeholder="https://github.com/username/repository"
                            required
                            className="w-full bg-slate-800 border border-white/10 rounded-lg px-4 py-2.5 text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-primary/50"
                        />
                    </div>

                    {/* GitHub Token */}
                    <div>
                        <label className="block text-sm font-medium text-slate-300 mb-2">
                            <Key className="w-4 h-4 inline mr-2" />
                            GitHub Personal Access Token (optional for public repos)
                        </label>
                        <input
                            type="password"
                            value={githubToken}
                            onChange={(e) => setGithubToken(e.target.value)}
                            placeholder="ghp_xxxxxxxxxxxxxxxxxxxx"
                            className="w-full bg-slate-800 border border-white/10 rounded-lg px-4 py-2.5 text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-primary/50"
                        />
                        <p className="text-xs text-slate-500 mt-1">Required for private repositories. Token will be saved locally.</p>
                    </div>

                    {/* Branch */}
                    <div>
                        <label className="block text-sm font-medium text-slate-300 mb-2">
                            <GitBranch className="w-4 h-4 inline mr-2" />
                            Branch
                        </label>
                        <input
                            type="text"
                            value={branch}
                            onChange={(e) => setBranch(e.target.value)}
                            placeholder="main"
                            required
                            className="w-full bg-slate-800 border border-white/10 rounded-lg px-4 py-2.5 text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-primary/50"
                        />
                    </div>

                    {/* HuggingFace API Key */}
                    <div>
                        <label className="block text-sm font-medium text-slate-300 mb-2">
                            <Cpu className="w-4 h-4 inline mr-2" />
                            HuggingFace API Key (GraphRAG Isolated)
                        </label>
                        <input
                            type="password"
                            value={hfApiKey}
                            onChange={(e) => setHfApiKey(e.target.value)}
                            placeholder="hf_xxxxxxxxxxxxxxxxxxxx"
                            required
                            className="w-full bg-slate-800 border border-white/10 rounded-lg px-4 py-2.5 text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-primary/50"
                        />
                        <p className="text-xs text-slate-500 mt-1">Isolated key for GraphRAG operations only. Will not affect main tool credentials.</p>
                    </div>

                    {/* Model Name */}
                    <div>
                        <label className="block text-sm font-medium text-slate-300 mb-2">
                            Model Name
                        </label>
                        <input
                            type="text"
                            value={modelName}
                            onChange={(e) => setModelName(e.target.value)}
                            placeholder="Qwen/Qwen2.5-32B-Instruct"
                            required
                            className="w-full bg-slate-800 border border-white/10 rounded-lg px-4 py-2.5 text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-primary/50"
                        />
                    </div>

                    {/* Actions */}
                    <div className="flex gap-3 pt-4">
                        <button
                            type="button"
                            onClick={onCancel}
                            className="flex-1 px-4 py-2.5 bg-white/5 hover:bg-white/10 text-slate-300 rounded-lg transition-colors font-medium"
                        >
                            Cancel
                        </button>
                        <button
                            type="submit"
                            className="flex-1 px-4 py-2.5 bg-primary hover:bg-primary/90 text-white rounded-lg transition-colors font-medium"
                        >
                            Save & Ingest
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}
