import os
import re
import json
import base64
import time
import asyncio
from typing import Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from groq import Groq
from deepgram import DeepgramClient, PrerecordedOptions, SpeakOptions
from dotenv import load_dotenv

from conversation_memory import ConversationMemory
from conversation_logger import ConversationLogger

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize clients
groq_key = os.environ.get("GROQ_API_KEY")
dg_key = os.environ.get("DEEPGRAM_API_KEY")

if not groq_key or not dg_key:
    print("ERROR: Missing API keys")
    exit(1)

groq = Groq(api_key=groq_key)
dg_client = DeepgramClient(api_key=dg_key)

print("Initializing HNSW memory...")
global_memory = ConversationMemory(dim=384, max_elements=100000)

try:
    global_memory.load()
    print(f"Loaded existing memory with {global_memory.current_id} conversations")
except FileNotFoundError:
    print("Starting with fresh memory")

print("Services initialized")

# --- Memory Management ---
class ConnectionManager:
    def __init__(self):
        self.active_connections = {}

    async def connect(self, websocket: WebSocket, connection_id: str):
        await websocket.accept()
        conv_logger = ConversationLogger()
        
        self.active_connections[connection_id] = {
            "page_context": "",
            "conversation_history": [],
            "logger": conv_logger,
            "session_id": f"anya_{connection_id}_{int(time.time())}"
        }
        print(f"Connected: {connection_id}")

    def disconnect(self, connection_id: str):
        if connection_id in self.active_connections:
            logger = self.active_connections[connection_id]["logger"]
            stats = logger.get_stats()
            print(f"Session stats: {stats}")
            
            del self.active_connections[connection_id]
            print(f"Disconnected: {connection_id}")

    def update_context(self, connection_id: str, text: str):
        if connection_id in self.active_connections:
            self.active_connections[connection_id]["page_context"] = text[:8000]

    def get_context(self, connection_id: str) -> str:
        return self.active_connections.get(connection_id, {}).get("page_context", "")

    def add_message(self, connection_id: str, role: str, content: str):
        if connection_id in self.active_connections:
            history = self.active_connections[connection_id]["conversation_history"]
            history.append({"role": role, "content": content})
            if len(history) > 12:
                self.active_connections[connection_id]["conversation_history"] = history[-12:]

    def get_history(self, connection_id: str) -> list:
        return self.active_connections.get(connection_id, {}).get("conversation_history", [])
    
    def get_logger(self, connection_id: str):
        return self.active_connections.get(connection_id, {}).get("logger")
    
    def get_session_id(self, connection_id: str) -> str:
        return self.active_connections.get(connection_id, {}).get("session_id", "")

manager = ConnectionManager()

# --- Core Functions ---
async def transcribe_audio(audio_data: bytes) -> Optional[str]:
    try:
        start = time.time()
        response = dg_client.listen.prerecorded.v("1").transcribe_file(
            {"buffer": audio_data},
            PrerecordedOptions(
                model="nova-2",
                smart_format=True,
                language="en",
                punctuate=True,
            )
        )
        
        if (response.results and response.results.channels and 
            response.results.channels[0].alternatives):
            text = response.results.channels[0].alternatives[0].transcript.strip()
            print(f"STT ({time.time()-start:.2f}s): {text}")
            return text
            
        return None
        
    except Exception as e:
        print(f"STT Error: {e}")
        return None

async def text_to_speech(text: str) -> Optional[bytes]:
    try:
        start = time.time()
        temp_file = f"temp_{int(time.time()*1000)}.wav"
        
        dg_client.speak.v("1").save(
            temp_file,
            {"text": text},
            SpeakOptions(
                model="aura-asteria-en",
                encoding="linear16",
                container="wav"
            )
        )
        
        with open(temp_file, "rb") as f:
            audio = f.read()
        
        os.remove(temp_file)
        print(f"TTS ({time.time()-start:.2f}s): Generated audio for full response")
        return audio
        
    except Exception as e:
        print(f"TTS Error: {e}")
        return None

async def store_in_memory(text: str, speaker: str, session_id: str):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        global_memory.add_conversation,
        text,
        speaker,
        session_id
    )
    await loop.run_in_executor(
        None,
        global_memory.save
    )
    print(f"Stored in memory: [{speaker}] {text[:50]}...")

def retrieve_relevant_context(query: str, top_k: int = 5) -> list:
    try:
        results = global_memory.retrieve(query, top_k=top_k)
        return results
    except Exception as e:
        print(f"Memory retrieval error: {e}")
        return []

def format_memory_context(relevant_memories: list) -> str:
    if not relevant_memories:
        return ""
    
    # Only use top 3 most relevant
    top_memories = relevant_memories[:3]
    
    context_parts = []
    for idx, mem in enumerate(top_memories, 1):
        similarity = mem.get('similarity', 0)
        text = mem.get('text', '')
        speaker = mem.get('speaker', 'unknown')
        
        if similarity > 0.3:  # Only use if similarity is reasonable
            context_parts.append(f"{speaker}: {text}")
    
    if context_parts:
        return "Previous relevant conversations:\n" + "\n".join(context_parts)
    return ""

# --- Routes ---
@app.get("/")
async def root():
    return {
        "status": "Server is running",
        "services": {
            "deepgram": True, 
            "groq": True,
            "memory": True
        },
        "memory_stats": {
            "total_conversations": global_memory.current_id
        }
    }

@app.get("/memory/stats")
async def memory_stats():
    """Get memory statistics"""
    return {
        "total_conversations": global_memory.current_id,
        "memory_size_mb": os.path.getsize("conversation_index.bin") / (1024*1024) if os.path.exists("conversation_index.bin") else 0
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    conn_id = f"conn_{id(websocket)}"
    await manager.connect(websocket, conn_id)
    
    try:
        while True:
            message = await websocket.receive()
            if "text" in message:
                try:
                    data = json.loads(message["text"])
                    
                    if data.get("type") == "page_update":
                        content = data.get("content", "")
                        manager.update_context(conn_id, content)
                        print(f"Context updated: {content[:200]}...")
                        await websocket.send_json({"type": "context_updated"})
                    elif data.get("type") == "ping":
                        await websocket.send_json({"type": "pong"})
                        
                except: 
                    pass

            if "bytes" in message:
                audio_data = message["bytes"]
                
                if not audio_data or len(audio_data) < 1000:
                    continue
                print(f"\n{'='*60}")
                request_start = time.time()
                user_text = await transcribe_audio(audio_data)
                if not user_text:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Could not understand audio"
                    })
                    continue
                logger = manager.get_logger(conn_id)
                if logger:
                    logger.log_message("user", user_text)
                
                await websocket.send_json({
                    "type": "user_transcript",
                    "text": user_text
                })
                print(f"Searching memory for relevant context...")
                relevant_memories = retrieve_relevant_context(user_text, top_k=5)
                
                memory_context = ""
                if relevant_memories:
                    memory_context = format_memory_context(relevant_memories)
                    print(f"Retrieved {len(relevant_memories)} relevant memories")
                else:
                    print(f"No relevant memories found")
                page_context = manager.get_context(conn_id)
                history = manager.get_history(conn_id)
                
                # Build system prompt with memory context
                system_prompt = f"""You are Anya from Spy X Family. Be helpful and cheerful. Keep responses SHORT (2-3 sentences max).

CURRENT PAGE CONTEXT:
{page_context[:2000] if page_context else "No page context available"}

{memory_context}

If the user asks about past conversations or things they told you before, use the previous conversations above to answer accurately."""

                messages = [
                    {"role": "system", "content": system_prompt}
                ] + history[-6:] + [
                    {"role": "user", "content": user_text}
                ]
                try:
                    llm_start = time.time()
                    completion = groq.chat.completions.create(
                        messages=messages,
                        model="llama-3.3-70b-versatile",
                        temperature=0.7,
                        max_tokens=150,
                        stream=False
                    )
                    
                    full_response = completion.choices[0].message.content.strip()
                    llm_time = time.time() - llm_start
                    print(f"LLM ({llm_time:.2f}s): {full_response}")
                    if logger:
                        logger.log_message("assistant", full_response)
                    
                    # Send full transcript
                    await websocket.send_json({
                        "type": "ai_transcript",
                        "text": full_response
                    })
                    print(f"Generating audio for complete response...")
                    audio_bytes = await text_to_speech(full_response)
                    
                    if audio_bytes:
                        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
                        await websocket.send_json({
                            "type": "audio_response",
                            "audio": audio_base64,
                            "complete": True
                        })
                        print(f"Sent complete audio response")
                    else:
                        await websocket.send_json({
                            "type": "error",
                            "message": "Failed to generate audio"
                        })
                    session_id = manager.get_session_id(conn_id)
                    await store_in_memory(user_text, "user", session_id)
                    await store_in_memory(full_response, "assistant", session_id)
                    
                    # Save to conversation history
                    manager.add_message(conn_id, "user", user_text)
                    manager.add_message(conn_id, "assistant", full_response)
                    total_time = time.time() - request_start
                    print(f"Complete in {total_time:.2f}s | Memory: {global_memory.current_id} total")
                    print(f"{'='*60}\n")
                    await websocket.send_json({
                        "type": "status",
                        "message": "complete"
                    })
                except Exception as e:
                    print(f"Error: {type(e).__name__}: {e}")
                    import traceback
                    traceback.print_exc()
                    await websocket.send_json({
                        "type": "error",
                        "message": str(e)
                    })

    except WebSocketDisconnect:
        manager.disconnect(conn_id)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(conn_id)
    finally:
        print("Final memory save...")
        global_memory.save()

if __name__ == "__main__":
    import uvicorn
    import signal
    
    print("\n" + "="*60)
    print("Anya Voice Server with HNSW Memory")
    print("="*60 + "\n")
    
    def shutdown_handler(signum, frame):
        print("\nShutting down...")
        print("Saving memory to disk...")
        global_memory.save()
        print("Memory saved. Goodbye!")
        exit(0)
    
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)
    
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")