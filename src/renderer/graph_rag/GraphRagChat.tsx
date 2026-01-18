import { useState, useEffect, useRef } from 'react';
import { Send, Bot, User, Loader2 } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import mermaid from 'mermaid';

interface GraphRagChatProps {
    onQuery: (query: string) => void;
    messages: { role: string; content: string }[];
    isTyping: boolean;
}

export function GraphRagChat({ onQuery, messages, isTyping }: GraphRagChatProps) {
    const [input, setInput] = useState('');
    const scrollRef = useRef<HTMLDivElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        // Scroll to bottom when messages change
        if (containerRef.current) {
            containerRef.current.scrollTop = containerRef.current.scrollHeight;
        }
    }, [messages, isTyping]);

    useEffect(() => {
        // Initialize mermaid diagrams after messages render
        const timer = setTimeout(() => {
            mermaid.run({ nodes: document.querySelectorAll('.mermaid') as NodeListOf<HTMLElement> });
        }, 100);
        return () => clearTimeout(timer);
    }, [messages]);

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (!input.trim() || isTyping) return;
        onQuery(input);
        setInput('');
    };

    return (
        <div className="flex flex-col h-full bg-slate-900/50 rounded-xl overflow-hidden border border-white/5">
            <div ref={containerRef} className="flex-1 overflow-y-auto p-4 space-y-6">
                {messages.map((msg, i) => (
                    <div key={i} className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                        {msg.role === 'assistant' && (
                            <div className="w-8 h-8 rounded-full bg-purple-500/20 flex items-center justify-center shrink-0">
                                <Bot className="w-5 h-5 text-purple-400" />
                            </div>
                        )}

                        <div className={`max-w-[80%] rounded-2xl px-4 py-3 ${msg.role === 'user'
                            ? 'bg-primary text-white'
                            : 'bg-slate-800/80 text-slate-200'
                            }`}>
                            <div className="prose prose-invert prose-sm max-w-none">
                                <ReactMarkdown
                                    components={{
                                        code({ node, inline, className, children, ...props }: any) {
                                            const match = /language-(\w+)/.exec(className || '')
                                            if (!inline && match && match[1] === 'mermaid') {
                                                return <div className="mermaid bg-white/5 p-4 rounded-lg">{String(children).replace(/\n$/, '')}</div>
                                            }
                                            return !inline && match ? (
                                                <div className="bg-black/30 p-2 rounded-lg text-xs font-mono overflow-x-auto">
                                                    {children}
                                                </div>
                                            ) : (
                                                <code className="bg-white/10 px-1 py-0.5 rounded text-xs" {...props}>
                                                    {children}
                                                </code>
                                            )
                                        }
                                    }}
                                >
                                    {msg.content}
                                </ReactMarkdown>
                            </div>
                        </div>

                        {msg.role === 'user' && (
                            <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center shrink-0">
                                <User className="w-5 h-5 text-primary" />
                            </div>
                        )}
                    </div>
                ))}

                {isTyping && (
                    <div className="flex gap-3">
                        <div className="w-8 h-8 rounded-full bg-purple-500/20 flex items-center justify-center shrink-0">
                            <Bot className="w-5 h-5 text-purple-400" />
                        </div>
                        <div className="bg-slate-800/50 rounded-2xl px-4 py-3 flex items-center gap-2 text-slate-400 text-sm">
                            <Loader2 className="w-4 h-4 animate-spin" />
                            Thinking...
                        </div>
                    </div>
                )}
                <div ref={scrollRef} />
            </div>

            <form onSubmit={handleSubmit} className="p-4 bg-slate-900/80 border-t border-white/5">
                <div className="relative">
                    <input
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        placeholder="Ask a business-level question (e.g., 'What happens when a user logs in?')"
                        className="w-full bg-slate-800 border border-white/10 rounded-xl px-4 py-3 pr-12 text-slate-200 outline-none focus:border-primary/50 placeholder:text-slate-500"
                    />
                    <button
                        type="submit"
                        disabled={!input.trim() || isTyping}
                        className="absolute right-2 top-1/2 -translate-y-1/2 p-2 hover:bg-white/10 text-primary rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        <Send className="w-5 h-5" />
                    </button>
                </div>
            </form>
        </div>
    );
}
