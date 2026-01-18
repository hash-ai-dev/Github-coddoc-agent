import { app, BrowserWindow, ipcMain } from 'electron';
import path from 'path';
import { spawn, ChildProcess } from 'child_process';
import fs from 'fs';
import Store from 'electron-store';

interface StoreSchema {
    githubToken: string;
    huggingfaceApiKey: string;
    confluenceUrl: string;
    confluenceApiToken: string;
    confluenceSpaceKey: string;
    modelName: string;
}

const store = new Store<StoreSchema>();

let mainWindow: BrowserWindow | null = null;
let pythonProcess: ChildProcess | null = null;

const isDev = !app.isPackaged;
const isWindows = process.platform === 'win32';

function getResourcePath(relativePath: string) {
    if (isDev) {
        // dist-electron/src/main/main.js -> ../../../ -> root
        return path.join(__dirname, '../../..', relativePath);
    }
    return path.join(process.resourcesPath, relativePath);
}

function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1200,
        height: 800,
        frame: false, // Frameless window
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            nodeIntegration: false,
            contextIsolation: true,
        },
        backgroundColor: '#0f172a',
        titleBarStyle: 'hidden',
    });

    if (isDev) {
        mainWindow.loadURL('http://localhost:5173');
        // mainWindow.webContents.openDevTools();
    } else {
        mainWindow.loadFile(path.join(__dirname, '../dist-vite/index.html'));
    }
}

// --- Python Management ---

function getPythonPath(backendPath: string) {
    if (isWindows) {
        return path.join(backendPath, 'env', 'Scripts', 'python.exe');
    }
    return path.join(backendPath, 'env', 'bin', 'python');
}

function getPipPath(backendPath: string) {
    if (isWindows) {
        return path.join(backendPath, 'env', 'Scripts', 'pip.exe');
    }
    return path.join(backendPath, 'env', 'bin', 'pip');
}

async function startPythonBackend() {
    const backendPath = getResourcePath('backend');
    const agentScript = path.join(backendPath, 'agent.py');
    const pythonExec = getPythonPath(backendPath);
    const requirementsRequest = path.join(backendPath, 'requirements.txt');

    // 1. Check if env exists
    const envPath = path.join(backendPath, 'env');
    const envExists = fs.existsSync(envPath);

    if (!envExists) {
        mainWindow?.webContents.send('python-system', { status: 'installing', message: 'Creating virtual environment...' });

        // Create Venv
        await new Promise<void>((resolve, reject) => {
            const venv = spawn('python', ['-m', 'venv', 'env'], { cwd: backendPath });
            venv.on('close', (code) => {
                if (code === 0) resolve();
                else reject(new Error(`Venv creation failed with code ${code}`));
            });
        });

        mainWindow?.webContents.send('python-system', { status: 'installing', message: 'Installing dependencies...' });

        // Install Requirements
        // Note: This relies on internet connection
        const pipExec = getPipPath(backendPath);
        await new Promise<void>((resolve, reject) => {
            const pip = spawn(pipExec, ['install', '-r', 'requirements.txt'], { cwd: backendPath });
            pip.stdout.on('data', (data) => console.log(`pip: ${data}`));
            pip.stderr.on('data', (data) => console.error(`pip err: ${data}`));

            pip.on('close', (code) => {
                if (code === 0) resolve();
                else reject(new Error(`Pip install failed with code ${code}`));
            });
        });
    }

    // 2. Start Agent
    mainWindow?.webContents.send('python-system', { status: 'starting', message: 'Starting Agent...' });

    // Ensure we use the venv python
    pythonProcess = spawn(pythonExec, ['-u', agentScript], {
        cwd: backendPath,
        env: { ...process.env, PYTHONUNBUFFERED: '1' }
    });

    // Helper for safe IPC sending
    const safeSend = (channel: string, ...args: any[]) => {
        if (mainWindow && !mainWindow.isDestroyed()) {
            mainWindow.webContents.send(channel, ...args);
        }
    };

    pythonProcess.stdout?.on('data', (data) => {
        const lines = data.toString().split('\n');
        lines.forEach((line: string) => {
            line = line.trim();
            if (!line) return;
            try {
                const json = JSON.parse(line);
                // Route message based on type
                if (json.type === 'log') safeSend('python-log', json.payload);
                else if (json.type === 'progress') safeSend('python-progress', json.payload);
                else if (json.type === 'system') safeSend('python-system', json.payload);
                else if (json.type === 'pong') safeSend('python-status', json.payload);
                else if (json.type === 'success') safeSend('python-status', json.payload);
                else if (json.type === 'repos_list') safeSend('python-repos', json.payload);
                else if (json.type === 'error') {
                    safeSend('python-log', { level: 'error', message: json.payload.message });
                    safeSend('python-error', { message: json.payload.message });
                }
                else if (json.type === 'preview') safeSend('python-preview', json.payload);
                else if (json.type === 'documentation_complete') safeSend('python-doc-complete', json.payload);
                else if (json.type === 'upload_success') safeSend('python-upload-success', json.payload);
                else if (json.type === 'chat_response') safeSend('python-message', json);
                else if (json.type === 'caches_list') safeSend('python-message', json);
                else if (json.type === 'cache_cleared') safeSend('python-message', json);
                else if (json.type === 'graphrag_status') safeSend('python-message', json);
                else if (json.type === 'graphrag_response') safeSend('python-message', json);
                else if (json.type === 'graphrag_progress') safeSend('python-message', json);
                else console.log('Unknown Python Message:', json);
            } catch (e) {
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

app.whenReady().then(() => {
    createWindow();
    startPythonBackend().catch(err => {
        console.error('Failed to start python backend:', err);
        mainWindow?.webContents.send('python-system', { status: 'error', message: err.message });
    });

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
});

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

app.on('before-quit', () => {
    if (pythonProcess) {
        pythonProcess.kill();
    }
});

// --- IPC Send ---
ipcMain.on('to-python', (event, arg) => {
    if (pythonProcess && pythonProcess.stdin) {
        const msg = JSON.stringify(arg) + '\n';
        pythonProcess.stdin.write(msg);
    }
});

// --- Settings IPC ---
ipcMain.handle('get-settings', async () => {
    return {
        githubToken: (store as any).get('githubToken', ''),
        huggingfaceApiKey: (store as any).get('huggingfaceApiKey', ''),
        confluenceUrl: (store as any).get('confluenceUrl', ''),
        confluenceEmail: (store as any).get('confluenceEmail', ''),
        confluenceApiToken: (store as any).get('confluenceApiToken', ''),
        confluenceSpaceKey: (store as any).get('confluenceSpaceKey', ''),
        modelName: (store as any).get('modelName', 'Qwen/Qwen2.5-Coder-32B-Instruct')
    };
});

ipcMain.handle('save-settings', async (event, settings) => {
    (store as any).set('githubToken', settings.githubToken || '');
    (store as any).set('huggingfaceApiKey', settings.huggingfaceApiKey || '');
    (store as any).set('confluenceUrl', settings.confluenceUrl || '');
    (store as any).set('confluenceEmail', settings.confluenceEmail || '');
    (store as any).set('confluenceApiToken', settings.confluenceApiToken || '');
    (store as any).set('confluenceSpaceKey', settings.confluenceSpaceKey || '');
    (store as any).set('modelName', settings.modelName || 'Qwen/Qwen2.5-Coder-32B-Instruct');
    return { success: true };
});

ipcMain.on('open-external', (event, url) => {
    require('electron').shell.openExternal(url);
});
ipcMain.on('window-minimize', () => {
    mainWindow?.minimize();
});

ipcMain.on('window-maximize', () => {
    if (mainWindow?.isMaximized()) {
        mainWindow.unmaximize();
    } else {
        mainWindow?.maximize();
    }
});

ipcMain.on('window-close', () => {
    mainWindow?.close();
});
