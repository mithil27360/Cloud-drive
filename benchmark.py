import os
import time
import requests
import pandas as pd
import json
from typing import List, Dict
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_recall
)
from langchain_groq import ChatGroq
from langchain_community.embeddings import HuggingFaceEmbeddings
# Ragas v0.1+ pattern
# We might need to handle specific versions, but let's try strict kwargs first

# --- Configuration ---
# --- Configuration ---
BACKEND_URL = "http://127.0.0.1:8000/api/query"
AUTH_URL = "http://127.0.0.1:8000/auth/login"
USER_EMAIL = "qa_user@example.com" 
USER_PASS = "password123"

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# --- Questions for "Attention Is All You Need" ---
QUESTIONS = [
    "What is the dominant sequence transduction model based on?",
    "Describe the Transformer architecture.",
    "What is Scaled Dot-Product Attention?",
    "Why use self-attention?",
    "What dataset was used for training?",
    "How does the attention mechanism compare to recurrent layers?",
    "What is the role of the encoder and decoder stacks?",
    "Explain the Positional Encoding used in the model.",
    "What optimizer was used for training the Transformer?",
    "What are the advantages of the Transformer model over RNNs?",
    "What is multi-head attention?",
    "Did the model use convolutional layers?",
    "What hardware was used for training?",
    "How is the output probability distribution generated?",
    "What is label smoothing?",
] + [f"Test Question {i}" for i in range(16, 51)]

def login():
    """Authenticates and returns a session token."""
    # Use standard form data login for regular users (or check if updated to JSON)
    # The auth.py login endpoint expects OAuth2PasswordRequestForm (form-data)
    response = requests.post(AUTH_URL, data={"username": USER_EMAIL, "password": USER_PASS})
    if response.status_code != 200:
        raise Exception(f"Login failed: {response.text}")
    return response.json()["access_token"]

def run_benchmark():
    print("🚀 Starting Benchmark...")
    
    if not GROQ_API_KEY:
        print("❌ Error: GROQ_API_KEY environment variable not set.")
        return

    # 1. Setup RAGAS with Groq and HuggingFace Embeddings
    llm = ChatGroq(model="llama-3.3-70b-versatile", api_key=GROQ_API_KEY)
    
    # Initialize minimal embeddings for metrics that need them (Relevancy, Recall)
    # Using a small, fast model to avoid timeouts/memory issues
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    
    print("🔑 Authenticating...")
    try:
        token = login()
    except Exception as e:
        print(f"❌ Auth failed: {e}")
        return

    headers = {"Authorization": f"Bearer {token}"}
    
    results_data = []
    
    print(f"📊 Running {len(QUESTIONS)} questions...")
    
    for i, q in enumerate(QUESTIONS):
        print(f"[{i+1}/{len(QUESTIONS)}] Asking: {q}")
        
        try:
            # Call Backend
            payload = {"query": q}
            resp = requests.post(BACKEND_URL, json=payload, headers=headers)
            
            if resp.status_code != 200:
                print(f"  ❌ Request failed: {resp.status_code}")
                continue
                
            data = resp.json()
            answer = data.get("answer", "")
            sources = data.get("sources", [])
            metadata = data.get("metadata", {})
            
            # Extract contexts
            contexts = [s.get("page_content", "") for s in sources]
            
            # Prepare data for RAGAS
            results_data.append({
                "question": q,
                "answer": answer,
                "contexts": contexts,
                "ground_truth": "nan", # Placeholder for ground truth, required by some RAGAS metrics like context_recall
                "latency_retrieval": metadata.get("retrieval_time", 0),
                "latency_generation": metadata.get("generation_time", 0),
                "latency_total": metadata.get("total_time", 0)
            })
            
        except Exception as e:
            print(f"  ❌ Error: {e}")

    # 2. Convert to Dataset
    if not results_data:
        print("❌ No results collected.")
        return

    df = pd.DataFrame(results_data)
    dataset = Dataset.from_pandas(df)
    
    print("🧠 Running RAGAS Evaluation (Faithfulness, Answer Relevancy, Context Recall)...")
    
    try:
        scores = evaluate(
            dataset,
            metrics=[faithfulness, answer_relevancy, context_recall], # Added context_recall
            llm=llm, 
            embeddings=embeddings 
        )
        
        print("\n🏆 Benchmark Results:")
        print(scores)
        
        # Save results
        df_scores = scores.to_pandas()
        final_df = pd.concat([df, df_scores], axis=1)
        final_df.to_csv("benchmark_results.csv", index=False)
        print("\n✅ Results saved to benchmark_results.csv")
        
    except Exception as e:
        print(f"❌ RAGAS Evaluation failed: {e}")
        print("Saving raw latency data anyway...")
        df.to_csv("benchmark_raw_latency.csv", index=False)

    # Calculate Latency Stats
    avg_retrieval = df["latency_retrieval"].mean()
    avg_gen = df["latency_generation"].mean()
    avg_total = df["latency_total"].mean()
    
    print(f"\n⏱️ Latency Metrics:")
    print(f"  Average Retrieval: {avg_retrieval:.4f}s")
    print(f"  Average Generation: {avg_gen:.4f}s")
    print(f"  Average Total:      {avg_total:.4f}s")
    
if __name__ == "__main__":
    run_benchmark()
