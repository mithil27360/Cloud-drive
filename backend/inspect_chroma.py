
import os
import sys

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from app.rag.indexer import get_collection

def inspect():
    print("Connecting to ChromaDB...")
    try:
        col = get_collection()
        print(f"Collection count: {col.count()}")
        
        # Peek at 5 items
        res = col.peek(limit=5)
        
        if not res["ids"]:
            print("Collection is empty!")
            return

        print("\n--- Metadata Dump (First 5 chunks) ---")
        for i, meta in enumerate(res["metadatas"]):
            print(f"\nChunk {i}:")
            print(f"  ID: {res['ids'][i]}")
            print(f"  Metadata: {meta}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect()
