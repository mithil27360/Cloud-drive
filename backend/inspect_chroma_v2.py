
import sys
import os

# Ensure backend modules are loadable
sys.path.append("/app")

try:
    from app.rag.indexer import get_collection
    
    print("--- CHROMA METADATA INSPECTION ---")
    col = get_collection()
    count = col.count()
    print(f"Total Chunks: {count}")
    
    if count > 0:
        # Get first 10 items
        res = col.peek(limit=10)
        metas = res.get("metadatas", [])
        
        print(f"Inspecting {len(metas)} chunks:")
        for i, m in enumerate(metas):
            sec = m.get("section", "N/A")
            page = m.get("page", "N/A")
            fid = m.get("file_id", "N/A")
            print(f"[{i}] File: {fid} | Page: {page} | Section: '{sec}'")
            
    print("--- END INSPECTION ---")

except Exception as e:
    print(f"FATAL ERROR: {e}")
