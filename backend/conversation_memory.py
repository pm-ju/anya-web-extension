import hnswlib
import numpy as np
from sentence_transformers import SentenceTransformer
import pickle
from datetime import datetime
import logging
import time
import os

logger = logging.getLogger("hnsw-memory")

class ConversationMemory:
    def __init__(self, dim=384, max_elements=100000):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.dim = dim
        
        self.index = hnswlib.Index(space='cosine', dim=self.dim)
        self.index.init_index(
            max_elements=max_elements,
            ef_construction=200,
            M=32
        )
        self.index.set_ef(50)
        
        self.metadata = {}
        self.current_id = 0
        
    def add_conversation(self, text, speaker="user", session_id=None):
        start_time = time.perf_counter()
        
        embedding = self.model.encode(text, convert_to_numpy=True)
        self.index.add_items(embedding, [self.current_id])
        
        self.metadata[self.current_id] = {
            'text': text,
            'speaker': speaker,
            'timestamp': datetime.now().isoformat(),
            'session_id': session_id
        }
        
        self.current_id += 1
        
    def retrieve(self, query, top_k=3):
        if self.current_id == 0:
            return []
        
        start_time = time.perf_counter()
        
        query_embedding = self.model.encode(query, convert_to_numpy=True)
        labels, distances = self.index.knn_query(query_embedding, k=min(top_k, self.current_id))
        
        results = []
        for label, distance in zip(labels[0], distances[0]):
            results.append({
                **self.metadata[label],
                'similarity': 1 - distance
            })
        return results
    
    def save(self, index_path='conversation_index.bin', 
             metadata_path='conversation_metadata.pkl'):
        self.index.save_index(index_path)
        with open(metadata_path, 'wb') as f:
            pickle.dump({
                'metadata': self.metadata,
                'current_id': self.current_id
            }, f)
    
    def load(self, index_path='conversation_index.bin',
             metadata_path='conversation_metadata.pkl'):
        if not os.path.exists(index_path) or not os.path.exists(metadata_path):
            raise FileNotFoundError(f"Index files not found")
        
        self.index.load_index(index_path)
        with open(metadata_path, 'rb') as f:
            data = pickle.load(f)
            self.metadata = data['metadata']
            self.current_id = data['current_id']
