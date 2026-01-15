import React, { useState } from 'react';
import { Send, X, Check, Loader2, FileText, Eye, Edit2 } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import rehypeHighlight from 'rehype-highlight';

interface DocumentationEditorProps {
    documentation: {
        repo_url: string;
        repo_name: string;
        overview: string;
        file_docs: Record<string, string>;
    };
    onClose: () => void;
}

export const DocumentationEditor: React.FC<DocumentationEditorProps> = ({ documentation, onClose }) => {
    const [overview, setOverview] = useState(documentation.overview);
    const [fileDocs, setFileDocs] = useState(documentation.file_docs);
    const [isUploading, setIsUploading] = useState(false);
    const [uploadSuccess, setUploadSuccess] = useState(false);
    const [confluenceUrl, setConfluenceUrl] = useState('');

    // View state
    const [previewMode, setPreviewMode] = useState<{ [key: string]: boolean }>({
        'overview': true // Default to preview mode for overview
    });

    React.useEffect(() => {
        // Default all files to preview mode
        const initialPreviewState: { [key: string]: boolean } = { 'overview': true };
        Object.keys(documentation.file_docs).forEach(file => {
            initialPreviewState[file] = true;
        });
        setPreviewMode(initialPreviewState);

        if (window.electronAPI && window.electronAPI.onUploadSuccess) {
            window.electronAPI.onUploadSuccess((data: { message: string; confluence_url: string }) => {
                setIsUploading(false);
                setUploadSuccess(true);
                setConfluenceUrl(data.confluence_url);
            });
        }
    }, []);

    const togglePreview = (key: string) => {
        setPreviewMode(prev => ({
            ...prev,
            [key]: !prev[key]
        }));
    };

    const handleUpload = async () => {
        setIsUploading(true);

        // Fetch current settings from UI store
        const settings = await window.electronAPI.getSettings();

        window.electronAPI.sendCommand({
            type: 'upload_to_confluence',
            data: {
                repoUrl: documentation.repo_url,
                repoName: documentation.repo_name,
                overview: overview,
                fileDocs: fileDocs,
                settings // Pass UI settings to backend
            }
        });
    };

    const handleFileDocChange = (fileName: string, content: string) => {
        setFileDocs(prev => ({
            ...prev,
            [fileName]: content
        }));
    };

    if (uploadSuccess) {
        return (
            <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
                <div className="glass-panel p-8 max-w-md w-full text-center">
                    <div className="w-16 h-16 bg-green-500/20 rounded-full flex items-center justify-center mx-auto mb-4">
                        <Check className="w-8 h-8 text-green-400" />
                    </div>
                    <h2 className="text-2xl font-bold text-white mb-2">Documentation Posted!</h2>
                    <p className="text-slate-400 mb-6">Your documentation has been successfully uploaded to Confluence.</p>
                    <a
                        href="#"
                        onClick={(e) => { e.preventDefault(); window.electronAPI.openExternal(confluenceUrl); }}
                        className="text-primary hover:text-primary/80 underline block mb-4"
                    >
                        View in Confluence →
                    </a>
                    <button
                        onClick={onClose}
                        className="px-6 py-2 bg-primary hover:bg-primary/90 text-white rounded-lg font-medium transition-colors"
                    >
                        Close
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <div className="glass-panel w-full max-w-6xl h-[90vh] flex flex-col">
                {/* Header */}
                <div className="px-6 py-4 border-b border-white/10 flex justify-between items-center">
                    <div className="flex items-center gap-3">
                        <div className="p-2 bg-primary/20 rounded-lg">
                            <FileText className="w-5 h-5 text-primary" />
                        </div>
                        <div>
                            <h2 className="text-xl font-bold text-white">{documentation.repo_name} - Documentation</h2>
                            <p className="text-sm text-slate-400">Review and edit before posting to Confluence</p>
                        </div>
                    </div>
                    <button
                        onClick={onClose}
                        className="p-2 hover:bg-white/10 rounded-lg transition-colors"
                    >
                        <X className="w-5 h-5 text-slate-400" />
                    </button>
                </div>

                {/* Content */}
                <div className="flex-1 overflow-auto p-6 space-y-8 custom-scrollbar">
                    {/* Overview Section */}
                    <div className="bg-slate-900/40 border border-white/5 rounded-xl overflow-hidden font-sans">
                        <div className="flex items-center justify-between px-4 py-2 bg-white/5 border-b border-white/5">
                            <label className="text-sm font-medium text-white">Overview Documentation</label>
                            <button
                                onClick={() => togglePreview('overview')}
                                className="flex items-center gap-2 text-xs px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors"
                            >
                                {previewMode['overview'] ? (
                                    <><Edit2 className="w-3 h-3" /> Edit Mode</>
                                ) : (
                                    <><Eye className="w-3 h-3" /> Preview Mode</>
                                )}
                            </button>
                        </div>

                        {previewMode['overview'] ? (
                            <div className="p-4 prose prose-invert prose-sm max-w-none prose-headings:text-slate-200 prose-p:text-slate-300 prose-code:text-primary prose-pre:bg-slate-950/50 prose-a:text-primary">
                                <ReactMarkdown rehypePlugins={[rehypeHighlight]}>
                                    {overview}
                                </ReactMarkdown>
                            </div>
                        ) : (
                            <textarea
                                value={overview}
                                onChange={(e) => setOverview(e.target.value)}
                                className="w-full h-96 bg-transparent p-4 text-slate-300 font-mono text-sm focus:outline-none resize-none"
                                placeholder="Overview documentation..."
                            />
                        )}
                    </div>

                    {/* File Documentation Sections */}
                    {Object.entries(fileDocs).map(([fileName, content]) => (
                        <div key={fileName} className="bg-slate-900/40 border border-white/5 rounded-xl overflow-hidden font-sans">
                            <div className="flex items-center justify-between px-4 py-2 bg-white/5 border-b border-white/5">
                                <label className="text-sm font-medium text-white">{fileName}</label>
                                <button
                                    onClick={() => togglePreview(fileName)}
                                    className="flex items-center gap-2 text-xs px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors"
                                >
                                    {previewMode[fileName] ? (
                                        <><Edit2 className="w-3 h-3" /> Edit Mode</>
                                    ) : (
                                        <><Eye className="w-3 h-3" /> Preview Mode</>
                                    )}
                                </button>
                            </div>

                            {previewMode[fileName] ? (
                                <div className="p-4 prose prose-invert prose-sm max-w-none prose-headings:text-slate-200 prose-p:text-slate-300 prose-code:text-primary prose-pre:bg-slate-950/50 prose-a:text-primary">
                                    <ReactMarkdown rehypePlugins={[rehypeHighlight]}>
                                        {content}
                                    </ReactMarkdown>
                                </div>
                            ) : (
                                <textarea
                                    value={content}
                                    onChange={(e) => handleFileDocChange(fileName, e.target.value)}
                                    className="w-full h-80 bg-transparent p-4 text-slate-300 font-mono text-sm focus:outline-none resize-none"
                                    placeholder={`Documentation for ${fileName}...`}
                                />
                            )}
                        </div>
                    ))}
                </div>

                {/* Footer */}
                <div className="px-6 py-4 border-t border-white/10 flex justify-between items-center">
                    <p className="text-sm text-slate-400">
                        {Object.keys(fileDocs).length} file{Object.keys(fileDocs).length !== 1 ? 's' : ''} documented
                    </p>
                    <div className="flex gap-3">
                        <button
                            onClick={onClose}
                            className="px-6 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg font-medium transition-colors"
                        >
                            Cancel
                        </button>
                        <button
                            onClick={handleUpload}
                            disabled={isUploading}
                            className="px-6 py-2 bg-primary hover:bg-primary/90 disabled:bg-primary/50 text-white rounded-lg font-medium transition-colors flex items-center gap-2 disabled:cursor-not-allowed"
                        >
                            {isUploading ? (
                                <>
                                    <Loader2 className="w-4 h-4 animate-spin" />
                                    Posting...
                                </>
                            ) : (
                                <>
                                    <Send className="w-4 h-4" />
                                    Post to Confluence
                                </>
                            )}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
};
