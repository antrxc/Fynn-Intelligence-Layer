import re
from typing import List, Optional

class DocumentChunker:
    """Handles chunking of large documents for efficient processing."""

    def __init__(self, chunk_size: int = 4000, overlap: int = 200):
        self.chunk_size = chunk_size
        self.overlap = overlap
        try:
            import tiktoken
            self.tokenizer = tiktoken.get_encoding("cl100k_base")  # For Gemini models
        except ImportError:
            self.tokenizer = None

    def chunk_text(self, text: str) -> List[str]:
        """Chunk text into manageable pieces."""
        if self.tokenizer:
            tokens = self.tokenizer.encode(text)
            chunks = []
            for i in range(0, len(tokens), self.chunk_size - self.overlap):
                chunk_tokens = tokens[i:i + self.chunk_size]
                chunks.append(self.tokenizer.decode(chunk_tokens))
            return chunks
        else:
            # Fallback: character-based chunking
            words = re.findall(r'\S+', text)
            chunks = []
            current_chunk = []
            current_length = 0
            for word in words:
                if current_length + len(word) > self.chunk_size:
                    chunks.append(' '.join(current_chunk))
                    current_chunk = [word]
                    current_length = len(word)
                else:
                    current_chunk.append(word)
                    current_length += len(word) + 1
            if current_chunk:
                chunks.append(' '.join(current_chunk))
            return chunks

    def is_large_file(self, content: str, size_threshold: int = 10000000) -> bool:
        """Determine if file is large based on size or token count."""
        if len(content) > size_threshold:
            return True
        if self.tokenizer:
            return len(self.tokenizer.encode(content)) > 50000
        return False
