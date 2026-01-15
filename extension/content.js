let modal = null;
let websocket = null;
let mediaRecorder = null;
let audioChunks = [];
let isRecording = false;
let serverUrl = 'ws://localhost:8000/ws';

let audioQueue = [];
let isPlayingAudio = false;
let currentAudio = null;

async function enqueueAudio(base64Audio) {
  console.log(`🎵 Enqueued audio chunk. Queue size: ${audioQueue.length + 1}`);
  audioQueue.push(base64Audio);
  
  if (!isPlayingAudio) {
    processAudioQueue();
  }
}

async function processAudioQueue() {
  if (isPlayingAudio) {
    return;
  }
  
  if (audioQueue.length === 0) {
    updateStatus('ready', 'Ready for next question!');
    return;
  }
  
  isPlayingAudio = true;
  updateStatus('speaking', 'Anya is speaking...');
  
  while (audioQueue.length > 0) {
    const audioData = audioQueue.shift();
    
    if (currentAudio) {
      currentAudio.pause();
      currentAudio.src = '';
      currentAudio = null;
    }
    
    try {
      await playAudioChunk(audioData);
    } catch (error) {
      console.error('Playback error:', error);
    }
    
    if (audioQueue.length > 0) {
      await new Promise(resolve => setTimeout(resolve, 100));
    }
  }
  
  isPlayingAudio = false;
  updateStatus('ready', 'Ready for next question!');
}

function playAudioChunk(base64Audio) {
  return new Promise(async (resolve, reject) => {
    let audioUrl = null;
    
    try {
      const audioBlob = base64ToBlob(base64Audio, 'audio/wav');
      audioUrl = URL.createObjectURL(audioBlob);
      
      currentAudio = new Audio();
      currentAudio.preload = 'auto';
      
      const playbackPromise = new Promise((playResolve, playReject) => {
        let hasStartedPlaying = false;
        
        currentAudio.onloadedmetadata = () => {
          console.log(`Audio loaded: ${currentAudio.duration.toFixed(2)}s`);
        };
        
        currentAudio.oncanplay = async () => {
          if (hasStartedPlaying) return;
          hasStartedPlaying = true;
          
          try {
            await currentAudio.play();
          } catch (err) {
            console.error('Play failed:', err);
            playReject(err);
          }
        };
        
        currentAudio.onended = () => {
          playResolve();
        };
        
        currentAudio.onerror = (e) => {
          console.error('Audio error:', e);
          playReject(new Error('Audio playback error'));
        };
      });
      
      currentAudio.src = audioUrl;
      currentAudio.load();
      
      await playbackPromise;
      
      if (audioUrl) URL.revokeObjectURL(audioUrl);
      currentAudio = null;
      
      resolve();
      
    } catch (error) {
      console.error('Audio chunk error:', error);
      if (audioUrl) URL.revokeObjectURL(audioUrl);
      if (currentAudio) {
        currentAudio.pause();
        currentAudio.src = '';
        currentAudio = null;
      }
      reject(error);
    }
  });
}

function stopCurrentAudio() {
  if (currentAudio) {
    currentAudio.pause();
    currentAudio.currentTime = 0;
    currentAudio.src = '';
    currentAudio = null;
  }
  
  audioQueue = [];
  isPlayingAudio = false;
  updateStatus('ready', 'Ready to listen!');
}

function base64ToBlob(base64, mimeType) {
  const byteCharacters = atob(base64);
  const byteNumbers = new Array(byteCharacters.length);
  
  for (let i = 0; i < byteCharacters.length; i++) {
    byteNumbers[i] = byteCharacters.charCodeAt(i);
  }
  
  const byteArray = new Uint8Array(byteNumbers);
  return new Blob([byteArray], { type: mimeType });
}

// Create modal UI
function createModal() {
  if (modal) return;
  
  const overlay = document.createElement('div');
  overlay.id = 'Anya-modal-overlay';
  
  overlay.innerHTML = `
    <div id="Anya-modal">
      <div class="Anya-header">
        <h2>Call Anya</h2>
        <button class="Anya-close-btn" id="Anya-close">×</button>
      </div>
      
      <div class="Anya-status ready" id="Anya-status">
        <div class="Anya-status-icon">
          <div class="Anya-pulse"></div>
        </div>
        <p id="Anya-status-text">Ready to listen!</p>
      </div>
      
      <div class="Anya-transcript">
        <div id="Anya-transcript-content">
          <p class="Anya-info">Press "Start Recording" to talk with Anya about this page! 🎀</p>
        </div>
      </div>
      
      <div class="Anya-controls">
        <button class="Anya-control-btn" id="Anya-record-btn">
          🎙️ Start Recording
        </button>
        <button class="Anya-control-btn Anya-end-btn" id="Anya-end-btn">
          ❌ End Call
        </button>
      </div>
      
      <div class="Anya-footer">
        <small>Powered by Deepgram + Groq + HNSW Memory</small>
      </div>
    </div>
  `;
  
  document.body.appendChild(overlay);
  modal = overlay;
  
  document.getElementById('Anya-close').addEventListener('click', closeModal);
  document.getElementById('Anya-end-btn').addEventListener('click', closeModal);
  document.getElementById('Anya-record-btn').addEventListener('click', toggleRecording);
  
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) closeModal();
  });
  
  initWebSocket();
}

// WebSocket setup
function initWebSocket() {
  try {
    websocket = new WebSocket(serverUrl);
    
    websocket.onopen = () => {
      console.log('WebSocket connected');
      updateStatus('ready', 'Connected! Ready to talk 🎤');
      sendPageContext();
    };
    
    websocket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
      } catch (error) {
        console.error('Message parse error:', error);
      }
    };
    
    websocket.onerror = (error) => {
      console.error('WebSocket error:', error);
      updateStatus('ready', '❌ Connection error');
    };
    
    websocket.onclose = () => {
      websocket = null;
    };
    
  } catch (error) {
    console.error('WebSocket init error:', error);
    updateStatus('ready', '❌ Failed to connect');
  }
}

function handleWebSocketMessage(data) {
  switch (data.type) {
    case 'user_transcript':
      addMessage('user', data.text);
      break;
      
    case 'ai_transcript':
      addMessage('ai', data.text);
      break;
      
    case 'audio_response':
      playAudio(data.audio);
      break;
      
    case 'status':
      if (data.message === 'complete') {
        console.log('Server processing complete');
      }
      break;
      
    case 'error':
      updateStatus('ready', '❌ ' + data.message);
      addMessage('system', 'Error: ' + data.message);
      stopCurrentAudio();
      break;
      
    case 'context_updated':
      console.log('Page context updated');
      break;
  }
}

// Recording control
async function toggleRecording() {
  const btn = document.getElementById('Anya-record-btn');
  
  if (!isRecording) {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        } 
      });
      
      mediaRecorder = new MediaRecorder(stream, {
        mimeType: 'audio/webm;codecs=opus'
      });
      
      audioChunks = [];
      
      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunks.push(event.data);
        }
      };
      
      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
        
        stopCurrentAudio();
        
        if (websocket && websocket.readyState === WebSocket.OPEN) {
          updateStatus('ready', 'Processing...');
          websocket.send(audioBlob);
        }
        
        stream.getTracks().forEach(track => track.stop());
      };
      
      mediaRecorder.start();
      isRecording = true;
      
      btn.textContent = '⏹️ Stop Recording';
      btn.classList.add('recording');
      updateStatus('listening', 'Listening... 👂');
      
    } catch (error) {
      console.error('Microphone error:', error);
      updateStatus('ready', '❌ Microphone access denied');
    }
    
  } else {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      mediaRecorder.stop();
    }
    
    isRecording = false;
    btn.textContent = '🎙️ Start Recording';
    btn.classList.remove('recording');
  }
}

// UI updates
function updateStatus(state, text) {
  const statusDiv = document.getElementById('Anya-status');
  const statusText = document.getElementById('Anya-status-text');
  
  if (statusDiv && statusText) {
    statusDiv.className = `Anya-status ${state}`;
    statusText.textContent = text;
  }
}

function addMessage(type, text) {
  const container = document.getElementById('Anya-transcript-content');
  if (!container) return;
  
  const info = container.querySelector('.Anya-info');
  if (info) info.remove();
  
  const message = document.createElement('div');
  message.className = `Anya-message ${type}`;
  
  if (type !== 'system') {
    const label = document.createElement('div');
    label.className = 'Anya-message-label';
    label.textContent = type === 'user' ? 'You' : 'Anya';
    message.appendChild(label);
  }
  
  const textDiv = document.createElement('div');
  textDiv.className = 'Anya-message-text';
  textDiv.textContent = text;
  message.appendChild(textDiv);
  
  container.appendChild(message);
  
  const transcript = document.querySelector('.Anya-transcript');
  if (transcript) {
    transcript.scrollTop = transcript.scrollHeight;
  }
}

function sendPageContext() {
  if (!websocket || websocket.readyState !== WebSocket.OPEN) return;
  
  const pageTitle = document.title;
  const pageUrl = window.location.href;
  const bodyText = document.body.innerText || document.body.textContent;
  const cleanText = bodyText.replace(/\s+/g, ' ').trim();
  
  const context = `
Page: ${pageTitle}
URL: ${pageUrl}

Content:
${cleanText.substring(0, 5000)}
  `.trim();
  
  websocket.send(JSON.stringify({
    type: 'page_update',
    content: context
  }));
}

function closeModal() {
  stopCurrentAudio();
  
  if (isRecording && mediaRecorder) {
    mediaRecorder.stop();
    isRecording = false;
  }
  
  if (websocket) {
    websocket.close();
    websocket = null;
  }
  
  if (modal) {
    modal.remove();
    modal = null;
  }
}

// Listen for messages from popup
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'openModal') {
    createModal();
    sendResponse({ success: true });
  }
});

// Create floating button
function createFloatingButton() {
  const button = document.createElement('button');
  button.id = 'Anya-float-btn';
  button.innerHTML = '🎤';
  button.title = 'Call Anya';
  
  button.style.cssText = `
    position: fixed;
    bottom: 24px;
    right: 24px;
    width: 60px;
    height: 60px;
    border-radius: 50%;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border: none;
    color: white;
    font-size: 28px;
    cursor: pointer;
    box-shadow: 0 4px 20px rgba(102, 126, 234, 0.4);
    z-index: 2147483646;
    transition: all 0.3s ease;
    display: flex;
    align-items: center;
    justify-content: center;
  `;
  
  button.addEventListener('mouseenter', () => {
    button.style.transform = 'scale(1.1)';
    button.style.boxShadow = '0 6px 30px rgba(102, 126, 234, 0.6)';
  });
  
  button.addEventListener('mouseleave', () => {
    button.style.transform = 'scale(1)';
    button.style.boxShadow = '0 4px 20px rgba(102, 126, 234, 0.4)';
  });
  
  button.addEventListener('click', createModal);
  
  document.body.appendChild(button);
}

// Initialize on page load
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', createFloatingButton);
} else {
  createFloatingButton();
}

console.log('Call Anya content script loaded');