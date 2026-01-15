import React, { useState, useEffect } from 'react';
import { Save, Check, AlertCircle } from 'lucide-react';
import type { Settings } from '../types';

export const SettingsView: React.FC = () => {
    const [settings, setSettings] = useState<Settings>({
        githubToken: '',
        huggingfaceApiKey: '',
        confluenceUrl: '',
        confluenceEmail: '',
        confluenceApiToken: '',
        confluenceSpaceKey: '',
        modelName: 'Qwen/Qwen2.5-Coder-32B-Instruct'
    });
    const [isSaving, setIsSaving] = useState(false);
    const [saveStatus, setSaveStatus] = useState<'idle' | 'success' | 'error'>('idle');
    const [errorMsg, setErrorMsg] = useState('');

    useEffect(() => {
        loadSettings();
    }, []);

    const loadSettings = async () => {
        try {
            const loaded = await window.electronAPI.getSettings();
            setSettings(loaded);
        } catch (error) {
            console.error('Failed to load settings:', error);
            setErrorMsg('Failed to load settings');
            setSaveStatus('error');
        }
    };

    const handleSave = async () => {
        setIsSaving(true);
        setSaveStatus('idle');
        setErrorMsg('');

        try {
            await window.electronAPI.saveSettings(settings);
            setSaveStatus('success');
            setTimeout(() => setSaveStatus('idle'), 3000);
        } catch (error) {
            console.error('Failed to save settings:', error);
            setErrorMsg('Failed to save settings');
            setSaveStatus('error');
        } finally {
            setIsSaving(false);
        }
    };

    const handleChange = (field: keyof Settings, value: string) => {
        setSettings(prev => ({ ...prev, [field]: value }));
    };

    return (
        <div className="flex-1 glass-panel p-8 m-1 overflow-auto">
            <h2 className="text-2xl font-bold mb-6 text-white">Settings</h2>

            <div className="space-y-6 max-w-2xl">
                {/* GitHub Settings */}
                <div className="space-y-4">
                    <h3 className="text-lg font-medium text-slate-300">GitHub Integration</h3>

                    <div className="space-y-2">
                        <label className="block text-sm text-slate-400">GitHub Personal Access Token</label>
                        <input
                            type="password"
                            value={settings.githubToken}
                            onChange={(e) => handleChange('githubToken', e.target.value)}
                            placeholder="ghp_xxxxxxxxxxxxxxxxxxxx"
                            className="w-full bg-slate-900/50 border border-white/10 rounded p-3 text-white placeholder-slate-600 focus:border-primary focus:outline-none transition-colors"
                        />
                        <p className="text-xs text-slate-500">Required for accessing private repositories</p>
                    </div>
                </div>

                {/* AI Model Settings */}
                <div className="space-y-4">
                    <h3 className="text-lg font-medium text-slate-300">AI Model Configuration</h3>

                    <div className="space-y-2">
                        <label className="block text-sm text-slate-400">Hugging Face API Key</label>
                        <input
                            type="password"
                            value={settings.huggingfaceApiKey}
                            onChange={(e) => handleChange('huggingfaceApiKey', e.target.value)}
                            placeholder="hf_xxxxxxxxxxxxxxxxxxxx"
                            className="w-full bg-slate-900/50 border border-white/10 rounded p-3 text-white placeholder-slate-600 focus:border-primary focus:outline-none transition-colors"
                        />
                        <p className="text-xs text-slate-500">Required for AI-powered documentation generation</p>
                    </div>

                    <div className="space-y-2">
                        <label className="block text-sm text-slate-400">Model Name</label>
                        <input
                            type="text"
                            value={settings.modelName}
                            onChange={(e) => handleChange('modelName', e.target.value)}
                            placeholder="Qwen/Qwen2.5-Coder-32B-Instruct"
                            className="w-full bg-slate-900/50 border border-white/10 rounded p-3 text-white placeholder-slate-600 focus:border-primary focus:outline-none transition-colors"
                        />
                        <p className="text-xs text-slate-500">Hugging Face model identifier</p>
                    </div>
                </div>

                {/* Confluence Settings */}
                <div className="space-y-4">
                    <h3 className="text-lg font-medium text-slate-300">Confluence Integration</h3>

                    <div className="space-y-2">
                        <label className="block text-sm text-slate-400">Confluence Email</label>
                        <input
                            type="email"
                            value={settings.confluenceEmail}
                            onChange={(e) => handleChange('confluenceEmail', e.target.value)}
                            placeholder="your-email@example.com"
                            className="w-full bg-slate-900/50 border border-white/10 rounded p-3 text-white placeholder-slate-600 focus:border-primary focus:outline-none transition-colors"
                        />
                    </div>

                    <div className="space-y-2">
                        <label className="block text-sm text-slate-400">Confluence URL</label>
                        <input
                            type="text"
                            value={settings.confluenceUrl}
                            onChange={(e) => handleChange('confluenceUrl', e.target.value)}
                            placeholder="https://your-domain.atlassian.net"
                            className="w-full bg-slate-900/50 border border-white/10 rounded p-3 text-white placeholder-slate-600 focus:border-primary focus:outline-none transition-colors"
                        />
                    </div>

                    <div className="space-y-2">
                        <label className="block text-sm text-slate-400">Confluence API Token</label>
                        <input
                            type="password"
                            value={settings.confluenceApiToken}
                            onChange={(e) => handleChange('confluenceApiToken', e.target.value)}
                            placeholder="Your Confluence API token"
                            className="w-full bg-slate-900/50 border border-white/10 rounded p-3 text-white placeholder-slate-600 focus:border-primary focus:outline-none transition-colors"
                        />
                    </div>

                    <div className="space-y-2">
                        <label className="block text-sm text-slate-400">Confluence Space Key</label>
                        <input
                            type="text"
                            value={settings.confluenceSpaceKey}
                            onChange={(e) => handleChange('confluenceSpaceKey', e.target.value)}
                            placeholder="DOCS"
                            className="w-full bg-slate-900/50 border border-white/10 rounded p-3 text-white placeholder-slate-600 focus:border-primary focus:outline-none transition-colors"
                        />
                        <p className="text-xs text-slate-500">Space where documentation will be published</p>
                    </div>
                </div>

                {/* Save Button & Status */}
                <div className="flex items-center gap-4 pt-4">
                    <button
                        onClick={handleSave}
                        disabled={isSaving}
                        className="flex items-center gap-2 bg-primary hover:bg-primary/90 disabled:bg-primary/50 text-white px-6 py-3 rounded-lg transition-colors disabled:cursor-not-allowed"
                    >
                        {isSaving ? (
                            <>
                                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                Saving...
                            </>
                        ) : (
                            <>
                                <Save className="w-4 h-4" />
                                Save Settings
                            </>
                        )}
                    </button>

                    {saveStatus === 'success' && (
                        <div className="flex items-center gap-2 text-green-400">
                            <Check className="w-5 h-5" />
                            <span>Settings saved successfully!</span>
                        </div>
                    )}

                    {saveStatus === 'error' && (
                        <div className="flex items-center gap-2 text-red-400">
                            <AlertCircle className="w-5 h-5" />
                            <span>{errorMsg || 'Failed to save settings'}</span>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};
