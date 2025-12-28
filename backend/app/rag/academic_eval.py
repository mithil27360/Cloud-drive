import logging
import json
import time
from typing import List, Dict, Tuple
from dataclasses import dataclass
from collections import Counter
import pandas as pd

from .engine import query_documents
from .indexer import get_collection

logger = logging.getLogger(__name__)

@dataclass
class AcademicTestCase:
    query: str
    target_sections: List[str] # e.g. ["Methodology", "Introduction"]
    category: str # "Method", "Results", "Goal"

class AcademicEvaluator:
    """
    Research-Grade Evaluation for Academic RAG.
    
    Focus:
    1. Section Precision: Does a 'Method' question retrieve 'Method' chunks?
    2. Answer Grounding: (Verified via Auditor separately)
    3. Failure Analysis: Detailed report on WHY retrieval failed.
    """
    
    TEST_SET = [
        AcademicTestCase(
            query="What is the main problem addressed?",
            target_sections=["Abstract", "Introduction"],
            category="Goal"
        ),
        AcademicTestCase(
            query="What is the proposed method?",
            target_sections=["Methodology", "Proposed Approach", "Method"],
            category="Method"
        ),
        AcademicTestCase(
            query="How does it compare to baselines?",
            target_sections=["Experiments", "Results", "Comparison"],
            category="Results"
        ),
        AcademicTestCase(
            query="What are the limitations?",
            target_sections=["Discussion", "Conclusion", "Limitations"],
            category="Critique"
        )
    ]
    
    def __init__(self):
        self.results = []
        self.failure_log = []

    def run_eval(self, user_id: int):
        """Execute the battery of academic tests."""
        logger.info(f"Starting Academic Eval for User {user_id}")
        
        scores = {
            "Method": [],
            "Results": [],
            "Goal": [],
            "Critique": []
        }
        
        for case in self.TEST_SET:
            t0 = time.time()
            
            # Execute RAG Retrieval
            # We care about the *retrieved chunks* (sources), not just the answer.
            # engine query returns list of dicts with 'metadata'
            retrieved_docs = query_documents(case.query, user_id, n_results=5)
            
            # Check Section Precision
            precision = self._calculate_section_precision(retrieved_docs, case.target_sections)
            
            # Log Result
            scores[case.category].append(precision)
            
            self._analyze_failure(case, retrieved_docs, precision)
            
        return self._generate_report(scores)

    def _calculate_section_precision(self, docs: List[Dict], targets: List[str]) -> float:
        """
        Fraction of retrieved docs that belong to target/relevant sections.
        Heuristic: Partial string match on section title.
        """
        if not docs:
            return 0.0
            
        hits = 0
        for doc in docs:
            section = doc.get("metadata", {}).get("section", "Unknown")
            # Loose match
            if any(t.lower() in section.lower() for t in targets):
                hits += 1
                
        return hits / len(docs)

    def _analyze_failure(self, case: AcademicTestCase, docs: List[Dict], precision: float):
        """Log failure cases for research analysis."""
        if precision < 0.5: # Threshold for 'Failure'
            retrieved_sections = [d.get("metadata", {}).get("section", "None") for d in docs]
            
            failure_entry = {
                "query": case.query,
                "expected": case.target_sections,
                "got_sections": retrieved_sections,
                "retrieved_excerpts": [d.get("content", "")[:50] for d in docs],
                "reason": self._diagnose_reason(case, retrieved_sections)
            }
            self.failure_log.append(failure_entry)

    def _diagnose_reason(self, case: AcademicTestCase, actual: List[str]) -> str:
        """Heuristic diagnosis of failure."""
        flat_actual = " ".join(actual).lower()
        if "reference" in flat_actual:
            return "Citation Pollution (Retrieved References)"
        if "abstract" in flat_actual and case.category == "Method":
            return "Abstract Bias (Method details usually deep in doc)"
        return "Semantic Drift"

    def _generate_report(self, scores: Dict) -> str:
        """Generate Research-Style Markdown Report."""
        
        # Calculate Aggregates
        avg_scores = {k: (sum(v)/len(v) if v else 0.0) for k, v in scores.items()}
        total_p = sum(avg_scores.values()) / len(avg_scores)
        
        report = f"""
# 🎓 Academic RAG Evaluation Report

## 1. Retrieval Accuracy via Section Alignment
| Category | Section Precision | Status |
|----------|-------------------|--------|
| **Goal** (Intro/Abstract) | {avg_scores['Goal']:.2%} | {"✅" if avg_scores['Goal']>0.7 else "⚠️"} |
| **Method** (Methodology) | {avg_scores['Method']:.2%} | {"✅" if avg_scores['Method']>0.7 else "⚠️"} |
| **Results** (Experiments) | {avg_scores['Results']:.2%} | {"✅" if avg_scores['Results']>0.7 else "⚠️"} |

**Overall Precision**: {total_p:.2%}

## 2. Failure Analysis (Research Signal)
Systematic failures identified in this run:

"""
        if not self.failure_log:
            report += "*No systemic failures detected. System is robust.*\n"
        else:
            for f in self.failure_log:
                report += f"- **Query**: '{f['query']}'\n"
                report += f"  - **Expected Sections**: {f['expected']}\n"
                report += f"  - **Actual Retrieved**: {f['got_sections']}\n"
                report += f"  - **Diagnosis**: {f['reason']}\n\n"
                
        return report

# Singleton
academic_evaluator = AcademicEvaluator()

if __name__ == "__main__":
    # Test Run
    print(academic_evaluator.run_eval(user_id=1))
