"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const electron_1 = require("electron");
const path_1 = __importDefault(require("path"));
const child_process_1 = require("child_process");
const fs_1 = __importDefault(require("fs"));
const electron_store_1 = __importDefault(require("electron-store"));
const store = new electron_store_1.default();
let mainWindow = null;
let pythonProcess = null;
const isDev = !electron_1.app.isPackaged;
const isWindows = process.platform === 'win32';
function getResourcePath(relativePath) {
    if (isDev) {
        // dist-electron/src/main/main.js -> ../../../ -> root
        return path_1.default.join(__dirname, '../../..', relativePath);
    }
    return path_1.default.join(process.resourcesPath, relativePath);
}
function createWindow() {
    mainWindow = new electron_1.BrowserWindow({
        width: 1200,
        height: 800,
        frame: false, // Frameless window
        webPreferences: {
            preload: path_1.default.join(__dirname, 'preload.js'),
            nodeIntegration: false,
            contextIsolation: true,
        },
        backgroundColor: '#0f172a',
        titleBarStyle: 'hidden',
    });
    if (isDev) {
        mainWindow.loadURL('http://localhost:5173');
        // mainWindow.webContents.openDevTools();
    }
    else {
        mainWindow.loadFile(path_1.default.join(__dirname, '../dist-vite/index.html'));
    }
}
// --- Python Management ---
function getPythonPath(backendPath) {
    if (isWindows) {
        return path_1.default.join(backendPath, 'env', 'Scripts', 'python.exe');
    }
    return path_1.default.join(backendPath, 'env', 'bin', 'python');
}
function getPipPath(backendPath) {
    if (isWindows) {
        return path_1.default.join(backendPath, 'env', 'Scripts', 'pip.exe');
    }
    return path_1.default.join(backendPath, 'env', 'bin', 'pip');
}
async function startPythonBackend() {
    const backendPath = getResourcePath('backend');
    const agentScript = path_1.default.join(backendPath, 'agent.py');
    const pythonExec = getPythonPath(backendPath);
    const requirementsRequest = path_1.default.join(backendPath, 'requirements.txt');
    // 1. Check if env exists
    const envPath = path_1.default.join(backendPath, 'env');
    const envExists = fs_1.default.existsSync(envPath);
    if (!envExists) {
        mainWindow?.webContents.send('python-system', { status: 'installing', message: 'Creating virtual environment...' });
        // Create Venv
        await new Promise((resolve, reject) => {
            const venv = (0, child_process_1.spawn)('python', ['-m', 'venv', 'env'], { cwd: backendPath });
            venv.on('close', (code) => {
                if (code === 0)
                    resolve();
                else
                    reject(new Error(`Venv creation failed with code ${code}`));
            });
        });
        mainWindow?.webContents.send('python-system', { status: 'installing', message: 'Installing dependencies...' });
        // Install Requirements
        // Note: This relies on internet connection
        const pipExec = getPipPath(backendPath);
        await new Promise((resolve, reject) => {
            const pip = (0, child_process_1.spawn)(pipExec, ['install', '-r', 'requirements.txt'], { cwd: backendPath });
            pip.stdout.on('data', (data) => console.log(`pip: ${data}`));
            pip.stderr.on('data', (data) => console.error(`pip err: ${data}`));
            pip.on('close', (code) => {
                if (code === 0)
                    resolve();
                else
                    reject(new Error(`Pip install failed with code ${code}`));
            });
        });
    }
    // 2. Start Agent
    mainWindow?.webContents.send('python-system', { status: 'starting', message: 'Starting Agent...' });
    // Ensure we use the venv python
    pythonProcess = (0, child_process_1.spawn)(pythonExec, ['-u', agentScript], {
        cwd: backendPath,
        env: { ...process.env, PYTHONUNBUFFERED: '1' }
    });
    // Helper for safe IPC sending
    const safeSend = (channel, ...args) => {
        if (mainWindow && !mainWindow.isDestroyed()) {
            mainWindow.webContents.send(channel, ...args);
        }
    };
    pythonProcess.stdout?.on('data', (data) => {
        const lines = data.toString().split('\n');
        lines.forEach((line) => {
            line = line.trim();
            if (!line)
                return;
            try {
                const json = JSON.parse(line);
                // Route message based on type
                if (json.type === 'log')
                    safeSend('python-log', json.payload);
                else if (json.type === 'progress')
                    safeSend('python-progress', json.payload);
                else if (json.type === 'system')
                    safeSend('python-system', json.payload);
                else if (json.type === 'pong')
                    safeSend('python-status', json.payload);
                else if (json.type === 'success')
                    safeSend('python-status', json.payload);
                else if (json.type === 'repos_list')
                    safeSend('python-repos', json.payload);
                else if (json.type === 'error') {
                    safeSend('python-log', { level: 'error', message: json.payload.message });
                    safeSend('python-error', { message: json.payload.message });
                }
                else if (json.type === 'preview')
                    safeSend('python-preview', json.payload);
                else if (json.type === 'documentation_complete')
                    safeSend('python-doc-complete', json.payload);
                else if (json.type === 'upload_success')
                    safeSend('python-upload-success', json.payload);
                else if (json.type === 'chat_response')
                    safeSend('python-message', json);
                else if (json.type === 'caches_list')
                    safeSend('python-message', json);
                else if (json.type === 'cache_cleared')
                    safeSend('python-message', json);
                else if (json.type === 'graphrag_status')
                    safeSend('python-message', json);
                else if (json.type === 'graphrag_response')
                    safeSend('python-message', json);
                else if (json.type === 'graphrag_progress')
                    safeSend('python-message', json);
                else
                    console.log('Unknown Python Message:', json);
            }
            catch (e) {
                console.log('Raw Python Output:', line);
                safeSend('python-log', { level: 'raw', message: line });
            }
        });
    });
    pythonProcess.stderr?.on('data', (data) => {
        console.error(`Python stderr: ${data}`);
        safeSend('python-log', { level: 'error', message: data.toString() });
    });
    pythonProcess.on('close', (code) => {
        console.log(`Python process exited with code ${code}`);
        safeSend('python-system', { status: 'stopped', message: `Process exited with code ${code}` });
    });
}
// --- App Lifecycle ---
electron_1.app.whenReady().then(() => {
    createWindow();
    startPythonBackend().catch(err => {
        console.error('Failed to start python backend:', err);
        mainWindow?.webContents.send('python-system', { status: 'error', message: err.message });
    });
    electron_1.app.on('activate', () => {
        if (electron_1.BrowserWindow.getAllWindows().length === 0)
            createWindow();
    });
});
electron_1.app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
        electron_1.app.quit();
    }
});
electron_1.app.on('before-quit', () => {
    if (pythonProcess) {
        pythonProcess.kill();
    }
});
// --- IPC Send ---
electron_1.ipcMain.on('to-python', (event, arg) => {
    if (pythonProcess && pythonProcess.stdin) {
        const msg = JSON.stringify(arg) + '\n';
        pythonProcess.stdin.write(msg);
    }
});
// --- Settings IPC ---
electron_1.ipcMain.handle('get-settings', async () => {
    return {
        githubToken: store.get('githubToken', ''),
        huggingfaceApiKey: store.get('huggingfaceApiKey', ''),
        confluenceUrl: store.get('confluenceUrl', ''),
        confluenceEmail: store.get('confluenceEmail', ''),
        confluenceApiToken: store.get('confluenceApiToken', ''),
        confluenceSpaceKey: store.get('confluenceSpaceKey', ''),
        modelName: store.get('modelName', 'Qwen/Qwen2.5-Coder-32B-Instruct')
    };
});
electron_1.ipcMain.handle('save-settings', async (event, settings) => {
    store.set('githubToken', settings.githubToken || '');
    store.set('huggingfaceApiKey', settings.huggingfaceApiKey || '');
    store.set('confluenceUrl', settings.confluenceUrl || '');
    store.set('confluenceEmail', settings.confluenceEmail || '');
    store.set('confluenceApiToken', settings.confluenceApiToken || '');
    store.set('confluenceSpaceKey', settings.confluenceSpaceKey || '');
    store.set('modelName', settings.modelName || 'Qwen/Qwen2.5-Coder-32B-Instruct');
    return { success: true };
});
electron_1.ipcMain.on('open-external', (event, url) => {
    require('electron').shell.openExternal(url);
});
electron_1.ipcMain.on('window-minimize', () => {
    mainWindow?.minimize();
});
electron_1.ipcMain.on('window-maximize', () => {
    if (mainWindow?.isMaximized()) {
        mainWindow.unmaximize();
    }
    else {
        mainWindow?.maximize();
    }
});
electron_1.ipcMain.on('window-close', () => {
    mainWindow?.close();
});
//# sourceMappingURL=main.js.map