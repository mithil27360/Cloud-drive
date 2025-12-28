import time
import logging
import json
import sqlite3
import statistics
from datetime import datetime
from collections import deque, Counter
from typing import Dict, List, Optional, Tuple
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

class MetricsTracker:
    """
    Production-grade metrics engine for RAG system observability.
    
    Features:
    - Persistent storage (SQLite) for long-term trends
    - In-memory aggregation for real-time dashboards
    - Thread-safe operational logging
    - Detailed latency histograms (P50, P90, P95, P99)
    - Error categorization and frequency tracking
    - Unsupported Claim Rate (UCR) tracking
    - Daily stats rollup
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, db_path: str = "metrics.db"):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super(MetricsTracker, cls).__new__(cls)
                    cls._instance.initialize(db_path)
        return cls._instance
    
    def initialize(self, db_path: str):
        """Initialize the metrics engine."""
        self.db_path = db_path
        self._setup_db()
        
        # Real-time windows (last 1000 requests)
        self.window_size = 1000
        self.rt_latencies = deque(maxlen=self.window_size)
        self.rt_failures = deque(maxlen=self.window_size)
        self.rt_ucr_events = deque(maxlen=self.window_size)
        
        # Error tracking
        self.error_counts = Counter()
        
    def _setup_db(self):
        """Create metrics schema if not exists."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS request_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp REAL,
                        latency_ms REAL,
                        status_code INT,
                        success BOOLEAN,
                        unsupported_claims INT,
                        error_type TEXT,
                        tokens_in INT,
                        tokens_out INT
                    )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_ts ON request_logs(timestamp)")
        except Exception as e:
            logger.error(f"Metrics DB Init Failed: {e}")

    def log_query(self, 
                 duration_sec: float, 
                 success: bool, 
                 unsupported_claims: int = 0,
                 status_code: int = 200,
                 error_type: Optional[str] = None,
                 tokens: Tuple[int, int] = (0, 0)):
        """
        Log a complete query event with full context.
        Async-safe logging to DB and memory.
        """
        latency_ms = duration_sec * 1000
        now = time.time()
        
        # 1. Update In-Memory Stats (Thread-safe via deque atomic appends)
        self.rt_latencies.append(latency_ms)
        self.rt_failures.append(0 if success else 1)
        self.rt_ucr_events.append(1 if unsupported_claims > 0 else 0)
        
        if error_type:
            self.error_counts[error_type] += 1
            
        # 2. Persist to DB (Fire and forget style - catch errors)
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO request_logs 
                    (timestamp, latency_ms, status_code, success, unsupported_claims, error_type, tokens_in, tokens_out)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (now, latency_ms, status_code, success, unsupported_claims, error_type, tokens[0], tokens[1]))
        except Exception as e:
            logger.error(f"Failed to persist metric: {e}")

    def get_realtime_stats(self) -> Dict:
        """Get P95 latency, error rates, and UCR from recent window."""
        if not self.rt_latencies:
            return {
                "status": "Waiting for traffic...",
                "samples": 0
            }
            
        count = len(self.rt_latencies)
        
        # Latency Stats
        sorted_lat = sorted(self.rt_latencies)
        p50 = sorted_lat[int(count * 0.5)]
        p95 = sorted_lat[int(count * 0.95)]
        p99 = sorted_lat[int(count * 0.99)]
        
        # Rates
        fail_rate = (sum(self.rt_failures) / count) * 100
        ucr_rate = (sum(self.rt_ucr_events) / count) * 100
        
        return {
            "window_samples": count,
            "latency": {
                "p50_ms": round(p50, 2),
                "p95_ms": round(p95, 2),
                "p99_ms": round(p99, 2),
                "avg_ms": round(sum(self.rt_latencies) / count, 2)
            },
            "reliability": {
                "error_rate_pct": round(fail_rate, 2),
                "unsupported_claim_rate_pct": round(ucr_rate, 2),
                "success_rate_pct": round(100 - fail_rate, 2)
            },
            "top_errors": self.error_counts.most_common(3)
        }

    def get_daily_rollup(self, days: int = 7) -> List[Dict]:
        """Generate daily aggregate statistics for reporting."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT 
                        date(datetime(timestamp, 'unixepoch')) as day,
                        COUNT(*) as total_reqs,
                        AVG(latency_ms) as avg_lat,
                        SUM(CASE WHEN success THEN 0 ELSE 1 END) as errors,
                        SUM(unsupported_claims) as hallucinations
                    FROM request_logs
                    WHERE timestamp > ?
                    GROUP BY day
                    ORDER BY day DESC
                """, (time.time() - (days * 86400),))
                
                rows = cursor.fetchall()
                return [
                    {
                        "date": r[0],
                        "requests": r[1],
                        "avg_latency_ms": round(r[2], 2),
                        "error_rate": round((r[3]/r[1])*100, 2),
                        "hallucination_rate": round((r[4]/r[1])*100, 2)
                    }
                    for r in rows
                ]
        except Exception as e:
            logger.error(f"Rollup failed: {e}")
            return []

    def export_report(self) -> str:
        """Generate a markdown report of system health."""
        stats = self.get_realtime_stats()
        daily = self.get_daily_rollup()
        
        report = f"""
# System Health Report

## Real-time Window (Last {stats.get('window_samples')} requests)
- **Lat P95**: {stats.get('latency', {}).get('p95_ms')} ms
- **Error Rate**: {stats.get('reliability', {}).get('error_rate_pct')}%
- **UCR (Unsupported Claims)**: {stats.get('reliability', {}).get('unsupported_claim_rate_pct')}%

## Daily Trends
| Date | Requests | Latency (Avg) | Error % | UCR % |
|------|----------|---------------|---------|-------|
"""
        for d in daily:
            report += f"| {d['date']} | {d['requests']} | {d['avg_latency_ms']}ms | {d['error_rate']}% | {d['hallucination_rate']}% |\n"
            
        return report

# Global Instance
metrics = MetricsTracker()
