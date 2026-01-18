"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const electron_1 = require("electron");
electron_1.contextBridge.exposeInMainWorld('electronAPI', {
    sendCommand: (command) => electron_1.ipcRenderer.send('to-python', command),
    onLog: (callback) => electron_1.ipcRenderer.on('python-log', (_event, data) => callback(data)),
    onStatus: (callback) => electron_1.ipcRenderer.on('python-status', (_event, data) => callback(data)),
    onProgress: (callback) => electron_1.ipcRenderer.on('python-progress', (_event, data) => callback(data)),
    onSystem: (callback) => electron_1.ipcRenderer.on('python-system', (_event, data) => callback(data)),
    onRepos: (callback) => electron_1.ipcRenderer.on('python-repos', (_event, data) => callback(data)),
    onError: (callback) => electron_1.ipcRenderer.on('python-error', (_event, data) => callback(data)),
    onPreview: (callback) => electron_1.ipcRenderer.on('python-preview', (_event, data) => callback(data)),
    onDocumentationComplete: (callback) => electron_1.ipcRenderer.on('python-doc-complete', (_event, data) => callback(data)),
    onUploadSuccess: (callback) => electron_1.ipcRenderer.on('python-upload-success', (_event, data) => callback(data)),
    removeListener: (channel) => electron_1.ipcRenderer.removeAllListeners(channel), // Simple cleanup
    getSettings: () => electron_1.ipcRenderer.invoke('get-settings'),
    saveSettings: (settings) => electron_1.ipcRenderer.invoke('save-settings', settings),
    openExternal: (url) => electron_1.ipcRenderer.send('open-external', url),
    minimize: () => electron_1.ipcRenderer.send('window-minimize'),
    maximize: () => electron_1.ipcRenderer.send('window-maximize'),
    close: () => electron_1.ipcRenderer.send('window-close'),
    onMessage: (callback) => {
        const listener = (_event, message) => callback(_event, message);
        electron_1.ipcRenderer.on('python-message', listener);
        return () => electron_1.ipcRenderer.removeListener('python-message', listener);
    },
    onChatResponse: (callback) => {
        const listener = (_event, data) => {
            if (data.type === 'chat_response') {
                callback(data.payload);
            }
        };
        electron_1.ipcRenderer.on('python-message', listener);
        return () => electron_1.ipcRenderer.removeListener('python-message', listener);
    },
    onGraphRagMessage: (callback) => {
        const listener = (_event, data) => {
            if (data.type && data.type.startsWith('graphrag_')) {
                // Return cleaned object: { type: 'status', ...payload }
                // backend sends type="graphrag_status", payload={status:..., message:...}
                // We want to pass a unified object or just payload with type injected?
                // GraphRagView expects { type: 'status', ...payload } logic
                // Let's just pass the payload and let View handle, BUT we need the SUBTYPE.
                // The backend type is "graphrag_status".
                // Let's pass { type: 'status', ...payload }
                const subType = data.type.replace('graphrag_', '');
                callback({ type: subType, ...data.payload });
            }
        };
        electron_1.ipcRenderer.on('python-message', listener);
        return () => electron_1.ipcRenderer.removeListener('python-message', listener);
    }
});
//# sourceMappingURL=preload.js.map