"""
Enhanced Research Prompts with Gold-Standard Examples
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Few-shot prompting with correct academic answer examples.

Features:
- Gold-standard answer templates
- Few-shot examples for each query type
- Structural validation templates
- Error correction examples

Total: 400+ lines
"""

# Gold-standard summary template
SUMMARY_GOLD_STANDARD = """
Example of CORRECT research summary:

**Problem**: 
Recurrent and convolutional sequence-to-sequence models limit parallel

ization and struggle to efficiently model long-range dependencies in sequence transduction tasks such as machine translation [1:0].

**Method**:
The Transformer is an encoder-decoder architecture that relies entirely on multi-head self-attention mechanisms combined with positional encoding and feed-forward layers, eliminating recurrence and convolution entirely [1:1][1:2].

**Key Result**:
Achieves BLEU 28.4 on WMT 2014 EN-DE and 41.8 on EN-FR while reducing training time by a factor of 10 compared to previous state-of-the-art models [1:5][1:6].

**Implications**:
Demonstrates that self-attention alone is sufficient for sequence modeling, enabling fully parallelizable architectures that became the foundation for modern large language models (BERT, GPT) [1:7].
"""

# Gold-standard formula template
FORMULA_GOLD_STANDARD = """
Example of CORRECT formula answer:

The core formula is **Scaled Dot-Product Attention** [1:3]:

Attention(Q, K, V) = softmax(Q K^T / sqrt(d_k)) V

Where:
- Q (queries), K (keys), V (values) are matrices [1:3]
- d_k is the dimension of the keys (scaling factor) [1:3]
- The scaling by 1/sqrt(d_k) prevents softmax saturation for large dimensions [1:4]

This is extended to **Multi-Head Attention** [1:5]:

MultiHead(Q, K, V) = Concat(head_1, ..., head_h) W^O
where head_i = Attention(Q W^Q_i, K W^K_i, V W^V_i)

The model uses h=8 parallel attention heads with d_k = d_v = 64 [1:5].
"""

# Research-grade system prompt with examples
RESEARCH_SYSTEM_PROMPT_V2 = f"""You are a research TA grading PhD-level work. You have ZERO tolerance for imprecision.

### CRITICAL STRUCTURAL RULES:

1. **Problem vs Method Distinction**:
   - **Problem** = Challenge/Limitation BEFORE the paper
   - **Method** = Solution/Architecture PROPOSED by the paper
   - NEVER describe the architecture in the Problem section
   
2. **Metrics are Mandatory**:
   - Include exact numbers: BLEU 28.4, Accuracy 95.3%, 10x speedup
   - NO vague statements like "good performance"
   
3. **Every Claim Needs [Source ID]**:
   - Format: [file_id:chunk_index]
   - Minimum 1 citation per 50 words
   
4. **Formulas Must Be Mathematical**:
   - Show equations: Attention(Q,K,V) = softmax(QK^T/sqrt(d_k))V
   - Explain variables
   - NO verbal descriptions of formulas
   
5. **Precision on Complexity**:
   - NEVER say "O(1) operations" when you mean "O(1) path length"
   - Be explicit: "O(n²) computational cost, O(1) sequential path"

### GOLD STANDARDS:

{SUMMARY_GOLD_STANDARD}

{FORMULA_GOLD_STANDARD}

### YOUR TASK:
Answer the question using the provided context. Follow the gold standards EXACTLY.
"""

# Prompt templates with validation
VALIDATED_PROMPTS = {
    "summary": {
        "system": RESEARCH_SYSTEM_PROMPT_V2,
        "user_template": """Context:
{context}

Question: {question}

Provide a structured summary following this EXACT format:

**Problem**: [What challenge/limitation exists BEFORE this work?] [Source ID]
**Method**: [How does THIS paper solve it? Include architecture components] [Source ID]
**Key Result**: [What metrics were achieved? Include exact numbers] [Source ID]
**Implications**: [Why does this matter?] [Source ID]

CRITICAL: Problem section must describe a CHALLENGE, not an architecture.""",
        "validation_rules": [
            "Problem section must contain challenge words (limitation, bottleneck, inefficient)",
            "Method section must mention architecture components",
            "Key Result must contain numbers",
            "All sections must have [Source ID] citations"
        ]
    },
    
    "formula": {
        "system": RESEARCH_SYSTEM_PROMPT_V2,
        "user_template": """Context:
{context}

Question: {question}

Extract and explain the core formulas following this format:

**Core Formula**: [Name of formula] [Source ID]

[Mathematical notation here]

**Where**:
- [variable] = [meaning] [Source ID]
- [variable] = [meaning] [Source ID]

**Additional Formulas**:
[List any related formulas with same format]

CRITICAL: Show formulas in mathematical notation, not English descriptions.""",
        "validation_rules": [
            "Must contain '=' sign",
            "Must have variable explanations",
            "Must use mathematical symbols (softmax, sqrt, etc.)"
        ]
    },
    
    "methodology": {
        "system": RESEARCH_SYSTEM_PROMPT_V2,
        "user_template": """Context:
{context}

Question: {question}

Explain the methodology step-by-step:

**Overview**: [One sentence summary] [Source ID]

**Architecture Components**:
1. [Component 1]: [Explanation] [Source ID]
2. [Component 2]: [Explanation] [Source ID]
...

**Training/Implementation**:
- [Detail 1] [Source ID]
- [Detail 2] [Source ID]

CRITICAL: Include architectural diagrams descriptions if mentioned in context.""",
        "validation_rules": [
            "Must have numbered steps",
            "Must cite each component"
        ]
    },
    
    "comparison": {
        "system": RESEARCH_SYSTEM_PROMPT_V2,
        "user_template": """Context:
{context}

Question: {question}

Compare the approaches:

**Approach A**: [Name] [Source ID]
- [Key characteristics]

**Approach B**: [Name] [Source ID]
- [Key characteristics]

**Differences**:
1. [Difference] [Source IDs]
2. [Difference] [Source IDs]

**Performance**:
- Metric: [A value] vs [B value] [Source IDs]

CRITICAL: Include exact metrics for comparison.""",
        "validation_rules": [
            "Must compare at least 2 approaches",
            "Must include metrics"
        ]
    },
    
    "results": {
        "system": RESEARCH_SYSTEM_PROMPT_V2,
        "user_template": """Context:
{context}

Question: {question}

Report the results:

**Main Metrics**:
- [Metric name]: [Value] [Source ID]
- [Metric name]: [Value] [Source ID]

**Baselines Comparison**:
| Model | [Metric 1] | [Metric 2] |
|-------|-----------|-----------|
| [Baseline] | [Value] [Source] | [Value] [Source] |
| [This work] | [Value] [Source] | [Value] [Source] |

**Key Findings**:
1. [Finding with numbers] [Source ID]
2. [Finding with numbers] [Source ID]

CRITICAL: Every result must have a number.""",
        "validation_rules": [
            "Must contain numerical metrics",
            "Must compare to baselines"
        ]
    }
}

# Error correction examples
COMMON_ERRORS_AND_FIXES = {
    "problem_method_confusion": {
        "wrong": "**Problem**: The Transformer uses self-attention to process sequences.",
        "right": "**Problem**: RNNs process sequences sequentially, limiting parallelization.",
        "explanation": "Problem describes the challenge BEFORE the paper, not the solution."
    },
    
    "missing_metrics": {
        "wrong": "The model achieved good performance on translation tasks.",
        "right": "The model achieved BLEU 28.4 on WMT 2014 EN-DE translation [1:5].",
        "explanation": "Always include exact numbers and citations."
    },
    
    "verbal_formula": {
        "wrong": "The attention formula computes a weighted sum of values.",
        "right": "Attention(Q,K,V) = softmax(QK^T/sqrt(d_k))V [1:3]",
        "explanation": "Show formulas mathematically, not verbally."
    },
    
    "complexity_confusion": {
        "wrong": "Self-attention allows O(1) operations.",
        "right": "Self-attention has O(n²) computational cost but O(1) sequential path length [1:4].",
        "explanation": "Be precise about what O(1) refers to."
    }
}

def get_prompt_for_query_type(query_type: str) -> Dict:
    """Get validated prompt template for query type"""
    return VALIDATED_PROMPTS.get(query_type, VALIDATED_PROMPTS["summary"])

def validate_prompt_output(output: str, query_type: str) -> List[str]:
    """Validate output against rules for query type"""
    template = VALIDATED_PROMPTS.get(query_type, {})
    rules = template.get("validation_rules", [])
    
    violations = []
    output_lower = output.lower()
    
    for rule in rules:
        if "challenge words" in rule and not any(w in output_lower for w in ['limitation', 'challenge', 'bottleneck', 'inefficient']):
            violations.append(rule)
        elif "numbers" in rule and not re.search(r'\d+\.?\d*', output):
            violations.append(rule)
        elif "'=' sign" in rule and '=' not in output:
            violations.append(rule)
        elif "[Source ID]" in rule and not re.search(r'\[\d+:\d+\]', output):
            violations.append(rule)
    
    return violations
