import React, { useEffect, useRef } from 'react';
import { Terminal as XTerminal } from 'xterm';
import { FitAddon } from 'xterm-addon-fit';
import 'xterm/css/xterm.css';

interface TerminalProps {
    className?: string;
}

export const Terminal: React.FC<TerminalProps> = ({ className }) => {
    const terminalRef = useRef<HTMLDivElement>(null);
    const xtermRef = useRef<XTerminal | null>(null);
    const fitAddonRef = useRef<FitAddon | null>(null);

    useEffect(() => {
        if (!terminalRef.current) return;

        // Initialize Terminal
        const term = new XTerminal({
            theme: {
                background: '#0f172a', // Match app background
                foreground: '#e2e8f0',
                cursor: '#3b82f6',
            },
            fontFamily: 'Menlo, Monaco, "Courier New", monospace',
            fontSize: 12,
            cursorBlink: true,
            scrollback: 1000,
            disableStdin: true, // Read-only logs for now
        });

        const fitAddon = new FitAddon();
        term.loadAddon(fitAddon);

        term.open(terminalRef.current);
        fitAddon.fit();

        xtermRef.current = term;
        fitAddonRef.current = fitAddon;

        // Window resize listener
        const handleResize = () => fitAddon.fit();
        window.addEventListener('resize', handleResize);

        // Initial greeting
        term.writeln('\x1b[1;34mDocAgent Terminal Initialized...\x1b[0m');

        // Subscribe to Logs
        const cleanupLog = window.electronAPI ? (() => {
            // We can wrap this in a safely typed way if we had the implementation context
            window.electronAPI.onLog((data) => {
                if (data.level === 'raw') {
                    term.writeln(data.message);
                } else if (data.level === 'error') {
                    term.writeln(`\x1b[1;31m[ERR] ${data.message}\x1b[0m`);
                } else {
                    term.writeln(`\x1b[32m[LOG] ${data.message}\x1b[0m`);
                }
            });

            window.electronAPI.onSystem((data) => {
                term.writeln(`\x1b[1;33m[SYS] ${data.message}\x1b[0m`);
            });

            return () => {
                window.electronAPI.removeListener('python-log');
                window.electronAPI.removeListener('python-system');
            };
        })() : undefined;

        return () => {
            window.removeEventListener('resize', handleResize);
            term.dispose();
            if (cleanupLog) cleanupLog();
        };
    }, []);

    // Monitor resize of container to refit
    useEffect(() => {
        if (fitAddonRef.current) {
            // Small delay to allow layout to settle
            setTimeout(() => fitAddonRef.current?.fit(), 100);
        }
    });

    return <div className={`h-full w-full ${className}`} ref={terminalRef} />;
};
