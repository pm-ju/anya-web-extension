# Call Anya: Browser Context Voice Assistant

This repository contains the source code for **Call Anya**, a real-time voice assistant that runs in your browser. It uses a Chrome Extension to "read" your active tab, allowing you to ask questions about the live webpage you are viewing.

The system is designed for speed and context awareness, utilizing WebSockets for low-latency communication and a vector database for long-term memory.

## Project Overview

* **Real-Time Performance:** Built using WebSockets to achieve a response latency of less than 500ms.
* **Browser Integration:** A Chrome Extension (built with TypeScript) captures the content of the active tab to provide context to the AI.
* **Long-Term Memory:** Implements an HNSW Vector Index (RAG) to store and retrieve past user conversations semantically, allowing the assistant to remember context across different sessions.

## Tech Stack

* **Backend:** Python (FastAPI)
* **Frontend/Extension:** TypeScript
* **Communication:** WebSockets
* **Database:** HNSW Vector DB (for RAG/Memory)

## Installation

### 1. Backend Setup

The backend handles the voice processing, memory storage, and WebSocket connections.

```bash
# Clone the repository
git clone [https://github.com/pm-ju/anya-web-extension.git](https://github.com/pm-ju/anya-web-extension.git)
cd anya-web-extension/backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start the server
uvicorn app.main:app --reload
```
### 2. Extension Setup

The extension captures browser context and handles audio input/output.

```bash
cd ../extension

# Install dependencies
npm install

# Build the extension
npm run build
```
## Loading into chrome:

1. Open Chrome and navigate to ```chrome://extensions```.
2. Enable "Developer mode" in the top right corner.
3. Click "Load unpacked".
4. Select the ```dist``` (or ```build```) folder inside the ```extension``` directory.

## Usage
1. Ensure the FastAPI backend is running on ```localhost```.
2. Open any webpage in Chrome.
3. Click the Call Anya extension icon or use the configured shortcut.
4. Ask a question. The assistant will read the page content, retrieve relevant past memories from the ```HNSW index```, and respond via voice.
