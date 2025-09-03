# Add to tools/file_processor.py
import io
import pandas as pd
from PyPDF2 import PdfReader
from typing import Tuple, Optional, List, Dict, Any

class FileProcessor:
    @staticmethod
    def process_file(content: bytes, mime_type: str, max_size_mb: int = 50) -> Tuple[str, dict]:
        # Check file size first
        if len(content) > max_size_mb * 1024 * 1024:
            raise ValueError(f"File exceeds maximum size of {max_size_mb}MB")
        
        if mime_type == 'application/pdf':
            return FileProcessor._process_pdf(content)
        elif mime_type in ['text/csv', 'application/vnd.ms-excel']:
            return FileProcessor._process_csv(content)
        elif 'text/' in mime_type:
            return FileProcessor._process_text(content)
        else:
            raise ValueError(f"Unsupported MIME type: {mime_type}")
    
    @staticmethod
    def _process_pdf(content: bytes) -> Tuple[str, dict]:
        """Extract text from PDF and create structured summary"""
        text = ""
        metadata = {}
        try:
            pdf_file = io.BytesIO(content)
            reader = PdfReader(pdf_file)
            metadata = reader.metadata or {}
            text = "\n".join([page.extract_text() for page in reader.pages])
            
            # Create smart summary for context
            summary = f"PDF Document: {metadata.get('/Title', 'Untitled')}\n"
            summary += f"Pages: {len(reader.pages)}\n"
            summary += f"Content preview: {text[:1000]}..."
            
            return summary, metadata
        except Exception as e:
            raise Exception(f"PDF processing failed: {str(e)}")
    
    @staticmethod
    def _process_csv(content: bytes) -> Tuple[str, dict]:
        """Parse CSV and create structured summary"""
        try:
            # Try to interpret content as string if it's bytes
            if isinstance(content, bytes):
                try:
                    content = content.decode('utf-8')
                except UnicodeDecodeError:
                    # If UTF-8 fails, try other common encodings
                    for encoding in ['latin-1', 'cp1252', 'iso-8859-1']:
                        try:
                            content = content.decode(encoding)
                            break
                        except UnicodeDecodeError:
                            continue
            
            # Try different CSV parsing options
            try:
                df = pd.read_csv(io.StringIO(content))
            except Exception:
                # Try with different delimiters
                for delimiter in [',', ';', '\t', '|']:
                    try:
                        df = pd.read_csv(io.StringIO(content), sep=delimiter)
                        # If we got here, the delimiter worked
                        break
                    except Exception:
                        continue
                else:
                    # None of the delimiters worked
                    raise ValueError("Could not parse CSV with common delimiters")
            
            # Generate summary and metadata
            summary = f"CSV Dataset Analysis:\n"
            summary += f"Shape: {df.shape[0]} rows, {df.shape[1]} columns\n"
            summary += f"Columns: {', '.join(df.columns.tolist())}\n"
            summary += f"Sample data:\n{df.head().to_string()}"
            
            # Basic statistics for numerical columns
            numeric_stats = {}
            for col in df.select_dtypes(include=['number']).columns:
                try:
                    numeric_stats[col] = {
                        "min": float(df[col].min()),
                        "max": float(df[col].max()),
                        "mean": float(df[col].mean()),
                        "null_count": int(df[col].isna().sum())
                    }
                except:
                    pass  # Skip if stats calculation fails
            
            metadata = {
                "rows": df.shape[0],
                "columns": df.shape[1],
                "column_names": df.columns.tolist(),
                "dtypes": {str(k): str(v) for k, v in df.dtypes.to_dict().items()},  # Convert to strings for JSON compatibility
                "numeric_stats": numeric_stats
            }
            
            return summary, metadata
        except Exception as e:
            # Fallback to treating as plain text
            try:
                if isinstance(content, bytes):
                    text_content = content.decode('utf-8', errors='ignore')
                else:
                    text_content = content
                    
                lines = text_content.splitlines()
                summary = f"CSV-like text (parse failed):\n"
                summary += f"Lines: {len(lines)}\n"
                summary += f"First 5 lines:\n" + "\n".join(lines[:5])
                
                return summary, {"error": str(e), "lines": len(lines)}
            except:
                raise Exception(f"CSV processing failed completely: {str(e)}")
# Add chunking strategy to FileProcessor
class SmartChunker:
    @staticmethod
    def chunk_content(content: str, max_tokens: int = 100000) -> List[Tuple[str, str]]:
        """Split content into manageable chunks with overlapping context"""
        # Simple character-based chunking (better: token-based)
        chunk_size = max_tokens * 4  # rough estimate
        chunks = []
        
        for i in range(0, len(content), chunk_size):
            chunk = content[i:i + chunk_size]
            chunks.append((f"chunk_{i//chunk_size}", chunk))
        
        return chunks
    
    @staticmethod
    def create_hierarchical_summary(chunks: List[Tuple[str, str]], llm_client) -> str:
        """Create a master summary from chunk summaries"""
        chunk_summaries = []
        for chunk_id, chunk_content in chunks:
            summary_prompt = f"Summarize this chunk in 2-3 sentences:\n\n{chunk_content[:5000]}"
            summary = llm_client.generate_content(summary_prompt)
            chunk_summaries.append(f"Chunk {chunk_id}: {summary}")
        
        master_prompt = f"Create a comprehensive summary from these chunk summaries:\n\n{' '.join(chunk_summaries)}"
        return llm_client.generate_content(master_prompt)