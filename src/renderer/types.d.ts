export interface Settings {
    githubToken: string;
    huggingfaceApiKey: string;
    confluenceUrl: string;
    confluenceEmail: string;
    confluenceApiToken: string;
    confluenceSpaceKey: string;
    modelName: string;
}

export interface IElectronAPI {
    sendCommand: (command: object) => void;
    onLog: (callback: (data: any) => void) => void;
    onStatus: (callback: (data: any) => void) => void;
    onProgress: (callback: (data: any) => void) => void;
    onSystem: (callback: (data: any) => void) => void;
    onRepos: (callback: (data: { repos: any[] }) => void) => void;
    onError: (callback: (data: { message: string }) => void) => void;
    onPreview: (callback: (data: { content: string }) => void) => void;
    onDocumentationComplete: (callback: (data: { message: string; documentation: any }) => void) => void;
    onUploadSuccess: (callback: (data: { message: string; confluence_url: string }) => void) => void;
    removeListener: (channel: string) => void;
    getSettings: () => Promise<Settings>;
    saveSettings: (settings: Settings) => Promise<{ success: boolean }>;
    openExternal: (url: string) => void;
    onMessage: (callback: (event: any, message: any) => void) => void;
    minimize: () => void;
    maximize: () => void;
    close: () => void;
    onChatResponse: (callback: (data: { answer: string }) => void) => () => void;
}

declare global {
    interface Window {
        electronAPI: IElectronAPI;
    }
}
