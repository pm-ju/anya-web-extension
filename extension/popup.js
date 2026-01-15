let serverUrl = 'http://localhost:8000';

async function checkServerStatus() {
  const statusIndicator = document.getElementById('status-indicator');
  const serverStatus = document.getElementById('server-status');
  const callBtn = document.getElementById('call-btn');
  const btnText = document.getElementById('btn-text');

  try {
    const response = await fetch(serverUrl, { method: 'GET' });
    const data = await response.json();

    if (data.status === 'Server is running') {
      statusIndicator.style.backgroundColor = '#4ade80';
      statusIndicator.classList.remove('loading');
      serverStatus.innerHTML = '<span id="status-indicator" style="background-color: #4ade80"></span> Connected';
      serverStatus.classList.add('connected');
      
      callBtn.disabled = false;
      btnText.textContent = '🎤 Start Call';

      if (!data.services.deepgram) {
        btnText.textContent = '⚠️ Deepgram Not Configured';
      } else if (!data.services.groq) {
        btnText.textContent = '⚠️ Groq Not Configured';
      } else if (!data.services.deepgram) {
        btnText.textContent = '⚠️ TTS Not Loaded';
      }
    }
  } catch (error) {
    statusIndicator.style.backgroundColor = '#fca5a5';
    statusIndicator.classList.remove('loading');
    serverStatus.innerHTML = '<span id="status-indicator" style="background-color: #fca5a5"></span> Offline';
    serverStatus.classList.add('disconnected');
    
    callBtn.disabled = true;
    btnText.textContent = '❌ Server Offline';
  }
}

document.getElementById('call-btn').addEventListener('click', async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  
  if (!tab) {
    alert('No active tab found');
    return;
  }

  chrome.tabs.sendMessage(tab.id, { action: 'openModal' }, (response) => {
    if (chrome.runtime.lastError) {
      console.error('Error:', chrome.runtime.lastError);
      alert('Failed to open Call Anya. Please refresh the page and try again.');
    } else {
      window.close();
    }
  });
});

document.getElementById('settings-btn').addEventListener('click', () => {
  const newUrl = prompt('Enter server URL:', serverUrl);
  if (newUrl) {
    serverUrl = newUrl;
    chrome.storage.local.set({ serverUrl: newUrl });
    checkServerStatus();
  }
});

chrome.storage.local.get(['serverUrl'], (result) => {
  if (result.serverUrl) {
    serverUrl = result.serverUrl;
  }
  checkServerStatus();
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'getServerUrl') {
    sendResponse({ serverUrl: serverUrl });
  }
});