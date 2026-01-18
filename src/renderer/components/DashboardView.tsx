import React from 'react';
import { Play, GitBranch, FileText, Zap } from 'lucide-react';

interface DashboardViewProps {
    repoUrl: string;
    setRepoUrl: (url: string) => void;
    handleStartAnalysis: () => void;
    isAnalyzing: boolean;
    progress: number;
}

export const DashboardView: React.FC<DashboardViewProps> = ({
    repoUrl,
    setRepoUrl,
    handleStartAnalysis,
    isAnalyzing,
    progress
}) => {
    return (
        <div className="flex-1 flex flex-col gap-6 overflow-auto">
            {/* Hero Section */}
            <div className="glass-panel p-8">
                <div className="flex items-center gap-3 mb-4">
                    <div className="p-3 bg-primary/20 rounded-xl">
                        <Zap className="w-6 h-6 text-primary" />
                    </div>
                    <div>
                        <h2 className="text-2xl font-bold text-white">AI-Powered Documentation</h2>
                        <p className="text-slate-400 text-sm">Automatically generate comprehensive documentation for any GitHub repository</p>
                    </div>
                </div>

                {/* Repository Input */}
                <div className="mt-6 space-y-4">
                    <div className="flex gap-3">
                        <div className="flex-1 relative">
                            <GitBranch className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-500" />
                            <input
                                type="text"
                                value={repoUrl}
                                onChange={(e) => setRepoUrl(e.target.value)}
                                placeholder="https://github.com/username/repository"
                                disabled={isAnalyzing}
                                className="w-full bg-slate-900/50 border border-white/10 rounded-lg pl-12 pr-4 py-4 text-white placeholder-slate-600 focus:border-primary focus:outline-none transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                            />
                        </div>
                        <button
                            onClick={handleStartAnalysis}
                            disabled={!repoUrl || isAnalyzing}
                            className="px-8 py-4 bg-primary hover:bg-primary/90 disabled:bg-primary/50 text-white rounded-lg font-medium transition-colors flex items-center gap-2 disabled:cursor-not-allowed"
                        >
                            <Play className="w-5 h-5" />
                            {isAnalyzing ? 'Analyzing...' : 'Analyze'}
                        </button>
                    </div>

                    {/* Progress Bar */}
                    {isAnalyzing && (
                        <div className="space-y-2">
                            <div className="flex justify-between text-sm">
                                <span className="text-slate-400">Processing repository...</span>
                                <span className="text-primary font-medium">{progress}%</span>
                            </div>
                            <div className="h-2 bg-slate-900/50 rounded-full overflow-hidden">
                                <div
                                    className="h-full bg-gradient-to-r from-primary to-cyan-400 transition-all duration-300 ease-out"
                                    style={{ width: `${progress}%` }}
                                />
                            </div>
                        </div>
                    )}
                </div>
            </div>

            {/* Features Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <FeatureCard
                    icon={<GitBranch className="w-6 h-6" />}
                    title="Repository Analysis"
                    description="Deep code analysis with structure extraction and language detection"
                />
                <FeatureCard
                    icon={<Zap className="w-6 h-6" />}
                    title="AI Generation"
                    description="Powered by Qwen model for intelligent documentation creation"
                />
                <FeatureCard
                    icon={<FileText className="w-6 h-6" />}
                    title="Confluence Upload"
                    description="Automatic publishing to your Confluence space"
                />
            </div>

            {/* Quick Start Guide */}
            <div className="glass-panel p-6">
                <h3 className="text-lg font-semibold text-white mb-4">Quick Start</h3>
                <div className="space-y-3 text-sm text-slate-300">
                    <div className="flex items-start gap-3">
                        <div className="w-6 h-6 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                            <span className="text-primary font-bold text-xs">1</span>
                        </div>
                        <div>
                            <p className="font-medium text-white">Configure Settings</p>
                            <p className="text-slate-400">Add your Hugging Face API key and Confluence credentials in the Settings tab</p>
                        </div>
                    </div>
                    <div className="flex items-start gap-3">
                        <div className="w-6 h-6 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                            <span className="text-primary font-bold text-xs">2</span>
                        </div>
                        <div>
                            <p className="font-medium text-white">Enter Repository URL</p>
                            <p className="text-slate-400">Paste any GitHub repository URL (public or private with token)</p>
                        </div>
                    </div>
                    <div className="flex items-start gap-3">
                        <div className="w-6 h-6 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                            <span className="text-primary font-bold text-xs">3</span>
                        </div>
                        <div>
                            <p className="font-medium text-white">Click Analyze</p>
                            <p className="text-slate-400">AI will analyze the code and generate documentation automatically</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

const FeatureCard: React.FC<{ icon: React.ReactNode; title: string; description: string }> = ({
    icon,
    title,
    description
}) => {
    return (
        <div className="glass-panel p-6 hover:border-primary/30 transition-colors">
            <div className="p-3 bg-primary/20 rounded-xl w-fit mb-4">
                {icon}
            </div>
            <h3 className="text-white font-semibold mb-2">{title}</h3>
            <p className="text-slate-400 text-sm">{description}</p>
        </div>
    );
};
