import json
import csv
from datetime import datetime
from pathlib import Path
import logging

logger = logging.getLogger("conversation-logger")

class ConversationLogger:
    def __init__(self, log_dir="conversation_logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.json_file = self.log_dir / f"conversation_{self.session_id}.json"
        self.csv_file = self.log_dir / f"conversation_{self.session_id}.csv"
        self.conversation_history = []
        self._init_csv()
        logger.info(f"Conversation logger initialized: {self.session_id}")
    
    def _init_csv(self):
        with open(self.csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'speaker', 'text', 'turn_number'])
    
    def log_message(self, speaker: str, text: str):
        timestamp = datetime.now().isoformat()
        turn_number = len(self.conversation_history) + 1
        
        entry = {
            'timestamp': timestamp,
            'speaker': speaker,
            'text': text,
            'turn_number': turn_number
        }
        self.conversation_history.append(entry)
        
        self._save_json()
        self._append_csv(entry)
        
        logger.info(f"Logged: [{speaker}] {text[:50]}...")
    
    def _save_json(self):
        with open(self.json_file, 'w', encoding='utf-8') as f:
            json.dump({
                'session_id': self.session_id,
                'total_turns': len(self.conversation_history),
                'conversation': self.conversation_history
            }, f, indent=2, ensure_ascii=False)
    
    def _append_csv(self, entry: dict):
        with open(self.csv_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                entry['timestamp'],
                entry['speaker'],
                entry['text'],
                entry['turn_number']
            ])
    
    def get_stats(self):
        total_turns = len(self.conversation_history)
        user_turns = sum(1 for msg in self.conversation_history if msg['speaker'] == 'user')
        assistant_turns = sum(1 for msg in self.conversation_history if msg['speaker'] == 'assistant')
        
        return {
            'session_id': self.session_id,
            'total_turns': total_turns,
            'user_turns': user_turns,
            'assistant_turns': assistant_turns,
            'duration_minutes': self._get_duration()
        }
    
    def _get_duration(self):
        if len(self.conversation_history) < 2:
            return 0
        
        start = datetime.fromisoformat(self.conversation_history[0]['timestamp'])
        end = datetime.fromisoformat(self.conversation_history[-1]['timestamp'])
        return round((end - start).total_seconds() / 60, 2)
