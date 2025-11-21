############################################
## ESM2 Embedding Module
## Input: protein sequences list
## Output: average token embeddings as pkl file
############################################

from transformers import AutoTokenizer, AutoModel
import torch
import numpy as np
import pickle
import gc
from typing import List, Optional
from pathlib import Path


class ESMEmbedder:
    """ESM2 based protein sequence embedding generator"""
    
    def __init__(self, model_name: str = "facebook/esm2_t6_8M_UR50D", device: Optional[str] = None):
        """
        Initialize ESM2 model
        
        Args:
            model_name: HuggingFace model name
            device: 'cuda' or 'cpu', auto-detect if None
        """
        self.device = device if device else ("cuda" if torch.cuda.is_available() else "cpu")
        
        print(f"Loading ESM2 model on {self.device}...")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name)
        self.model = self.model.to(self.device)
        self.model.eval()
        
        print(f"Model loaded successfully on {self.device}")
        if torch.cuda.is_available():
            print(f"CUDA memory allocated: {torch.cuda.memory_allocated()/1024**3:.2f} GB")
    
    def clean_sequence(self, sequence: str) -> str:
        """
        Clean protein sequence (keep only valid amino acids)
        
        Args:
            sequence: raw protein sequence
            
        Returns:
            cleaned sequence
        """
        valid_aa = set('ACDEFGHIKLMNPQRSTVWY*')
        return ''.join(c for c in sequence.upper() if c in valid_aa)
    
    def encode_single(self, sequence: str, max_length: int = 1024):
        """
        Encode single protein sequence to average token embedding
        
        Args:
            sequence: protein sequence
            max_length: maximum sequence length
            
        Returns:
            average token embedding as numpy array [1, embedding_dim]
        """
        if len(sequence) > max_length:
            sequence = sequence[:max_length]
        
        try:
            inputs = self.tokenizer(
                sequence,
                return_tensors="pt",
                padding=False,
                truncation=True,
                max_length=max_length
            )
            
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            with torch.no_grad():
                outputs = self.model(**inputs)
            
            avg_embedding = outputs.last_hidden_state.mean(dim=1)
            result = avg_embedding.cpu().numpy()
            
            del inputs, outputs, avg_embedding
            torch.cuda.empty_cache()
            
            return result
            
        except Exception as e:
            print(f"Error encoding sequence (length {len(sequence)}): {e}")
            return None
    
    def encode_batch(self, sequences: List[str], batch_size: int = 32, show_progress: bool = True):
        """
        Encode multiple protein sequences
        
        Args:
            sequences: list of protein sequences
            batch_size: number of sequences to process at once
            show_progress: whether to print progress
            
        Returns:
            list of average token embeddings
        """
        embeddings = []
        total = len(sequences)
        
        if show_progress:
            print(f"Processing {total} sequences...")
        
        for i in range(0, total, batch_size):
            batch = sequences[i:i+batch_size]
            
            for seq in batch:
                if seq and len(seq.strip()) > 0:
                    clean_seq = self.clean_sequence(seq)
                    if clean_seq:
                        emb = self.encode_single(clean_seq)
                        embeddings.append(emb)
                    else:
                        embeddings.append(None)
                else:
                    embeddings.append(None)
            
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                gc.collect()
            
            if show_progress and (i + batch_size) % (batch_size * 5) == 0:
                progress = min(i + batch_size, total) / total * 100
                print(f"Progress: {min(i + batch_size, total)}/{total} ({progress:.1f}%)")
        
        if show_progress:
            valid_count = sum(1 for emb in embeddings if emb is not None)
            print(f"Completed: {valid_count}/{total} valid embeddings")
        
        return embeddings
    
    def save_embeddings(self, file_name: str, embeddings: List[Optional[np.ndarray]], output_path: str):
        """
        Save embeddings to pickle file
        
        Args:
            embeddings: list of embeddings
            output_path: path to save pickle file
        """
        output_file = output_path + Path(file_name).stem + 'tags.txt'
        with open(output_file, 'wb') as f:
            pickle.dump(embeddings, f)
        
        valid_count = sum(1 for emb in embeddings if emb is not None)
        print(f"Saved {valid_count}/{len(embeddings)} embeddings to {output_file}")
    
    @staticmethod
    def load_embeddings(pkl_path: str):
        """
        Load embeddings from pickle file
        
        Args:
            pkl_path: path to pickle file
            
        Returns:
            list of embeddings
        """
        with open(pkl_path, 'rb') as f:
            embeddings = pickle.load(f)
        print(f"Loaded {len(embeddings)} embeddings from {pkl_path}")
        return embeddings


def embed_sequences(file_name: str, sequences: List[str], output_path: str, batch_size: int = 32):
    """
    Convenience function to embed sequences and save to file
    
    Args:
        sequences: list of protein sequences
        output_path: path to save embeddings
        batch_size: batch size for processing
        
    Returns:
        list of embeddings
    """
    embedder = ESMEmbedder()
    embeddings = embedder.encode_batch(sequences, batch_size=batch_size)
    embedder.save_embeddings(file_name, embeddings, output_path)
    return embeddings
