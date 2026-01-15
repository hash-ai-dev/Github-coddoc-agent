import { contextBridge, ipcRenderer } from 'electron';

contextBridge.exposeInMainWorld('electronAPI', {
    sendCommand: (command: object) => ipcRenderer.send('to-python', command),
    onLog: (callback: (data: any) => void) => ipcRenderer.on('python-log', (_event, data) => callback(data)),
    onStatus: (callback: (data: any) => void) => ipcRenderer.on('python-status', (_event, data) => callback(data)),
    onProgress: (callback: (data: any) => void) => ipcRenderer.on('python-progress', (_event, data) => callback(data)),
    onSystem: (callback: (data: any) => void) => ipcRenderer.on('python-system', (_event, data) => callback(data)),
    onRepos: (callback: (data: any) => void) => ipcRenderer.on('python-repos', (_event, data) => callback(data)),
    onError: (callback: (data: any) => void) => ipcRenderer.on('python-error', (_event, data) => callback(data)),
    onPreview: (callback: (data: any) => void) => ipcRenderer.on('python-preview', (_event, data) => callback(data)),
    onDocumentationComplete: (callback: (data: any) => void) => ipcRenderer.on('python-doc-complete', (_event, data) => callback(data)),
    onUploadSuccess: (callback: (data: any) => void) => ipcRenderer.on('python-upload-success', (_event, data) => callback(data)),
    removeListener: (channel: string) => ipcRenderer.removeAllListeners(channel), // Simple cleanup
    getSettings: () => ipcRenderer.invoke('get-settings'),
    saveSettings: (settings: any) => ipcRenderer.invoke('save-settings', settings),
    openExternal: (url: string) => ipcRenderer.send('open-external', url),
    minimize: () => ipcRenderer.send('window-minimize'),
    maximize: () => ipcRenderer.send('window-maximize'),
    close: () => ipcRenderer.send('window-close'),
    onMessage: (callback: (event: any, message: any) => void) => {
        const listener = (_event: any, message: any) => callback(_event, message);
        ipcRenderer.on('python-message', listener);
        return () => ipcRenderer.removeListener('python-message', listener);
    },
    onChatResponse: (callback: (data: any) => void) => {
        const listener = (_event: any, data: any) => {
            if (data.type === 'chat_response') {
                callback(data.payload);
            }
        };
        ipcRenderer.on('python-message', listener);
        return () => ipcRenderer.removeListener('python-message', listener);
    }
});
