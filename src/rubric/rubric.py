RUBRIC_STRUCTURE = {
    "Project": {"runs end-to-end without errors (python main.py --step all)": 20},
    "Tooling": {
        "Project developed in VS Code and published as a public GitHub repository": 2,
        "Anaconda environment created and used": 3,
        "At least 10 commits in the repository": 3,
        "At least one branch merged into main": 2,
    },
    "Standard Parts": {
        "Correct and complete README.md with all required sections": 5,
        "Correct requirements.txt with all libraries pinned": 4,
        "Correct config/.env with all required variables": 4,
        "Correct .gitignore excluding data/, *.json, and __pycache__/": 2,
    },
    "Code Structure": {
        "Repository follows the specified folder and file structure exactly": 10,
        "No file paths or thresholds hardcoded; all loaded from config/.env": 15,
    },
    "General Coding": {
        "All classes and methods have docstrings (proportional)": 7,
        "No global variables": 5,
        "No code duplication — each piece of logic exists in exactly one place": 8,
    },
    "Design Quality": {
        "All classes and methods specified in the instructions are implemented (proportional)": 3,
        "NGramModel.lookup() is the single source of backoff logic — not re-implemented in any other module": 3,
        "Normalizer.normalize() reused in Module 3 — not re-implemented": 2,
        "Dependency injection — NGramModel and Normalizer instantiated once in main() and passed in": 2,
    },
    "Extra Credit": {
        "Smoothing — any technique from Sections 3–6 of the reference paper": 5,
        "Streamlit UI — all specified PredictorUI methods implemented": 5,
        "Exception Handling — specific exception types and informative messages": 5,
        "Logging — LOG_LEVEL from .env with appropriate log levels": 5,
        "Model Evaluator — correct perplexity computation on held-out corpus": 5,
        "Unit Tests — per-method tests, all passing": 5,
    },
}

LLM_GRADED_CRITERIA = [
    "No file paths or thresholds hardcoded; all loaded from config/.env",
    "All classes and methods have docstrings (proportional)",
    "No global variables",
    "No code duplication — each piece of logic exists in exactly one place",
    "All classes and methods specified in the instructions are implemented (proportional)",
    "NGramModel.lookup() is the single source of backoff logic — not re-implemented in any other module",
    "Normalizer.normalize() reused in Module 3 — not re-implemented",
    "Dependency injection — NGramModel and Normalizer instantiated once in main() and passed in",
    "Smoothing — any technique from Sections 3–6 of the reference paper",
    "Streamlit UI — all specified PredictorUI methods implemented",
    "Exception Handling — specific exception types and informative messages",
    "Logging — LOG_LEVEL from .env with appropriate log levels",
    "Model Evaluator — correct perplexity computation on held-out corpus",
]

LLM_RUBRIC_PROMPT = """
You are an expert strict programming instructor evaluating a student's submission for the "N-Gram Next-Word Predictor" capstone project in Python. Your task is to evaluate the provided Python source code against the following specific criteria and assign a numeric score for each criterion based on the maximum points allowed. Return your evaluation in strict JSON format.

Evaluate the following Extra Credit criteria if they are implemented. Assign 0 points if not implemented.

Here are the criteria to evaluate via static code analysis:

**Code Structure (Max 25)**
- "No file paths or thresholds hardcoded; all loaded from config/.env" (15 pts): Check if paths like 'data/raw/', 'data/model/', model.json, config/.env, or thresholds like UNK_THRESHOLD, TOP_K, NGRAM_ORDER are hardcoded in the logic, instead of being cleanly separated or passed via dependency injection or dotenv reading.

**General Coding (Max 20)**
- "All classes and methods have docstrings (proportional)" (7 pts): Check all .py files in src/ for standard docstrings on classes and methods. Assign proportionally between 0 and 7.
- "No global variables" (5 pts): Ensure state is strictly passed via function arguments or class attributes.
- "No code duplication — each piece of logic exists in exactly one place" (8 pts): Look for copy-pasted backoff logic or text normalization code.

**Design Quality (Max 10)**
- "All classes and methods specified in the instructions are implemented (proportional)" (3 pts): Check for Normalizer, NGramModel, Predictor properties and methods.
- "NGramModel.lookup() is the single source of backoff logic — not re-implemented in any other module" (3 pts): Predictor should not have backoff falling loops, it just delegates to `lookup()`.
- "Normalizer.normalize() reused in Module 3 — not re-implemented" (2 pts): Module 3 (Predictor) must call `normalizer.normalize()`.
- "Dependency injection — NGramModel and Normalizer instantiated once in main() and passed in" (2 pts): Predictor.__init__ takes model, normalizer as args, instead of instantiating them itself.

**Extra Credit (Max 30)**
- "Smoothing — any technique from Sections 3–6 of the reference paper" (5 pts): Check if Katz Backoff, Laplace, or other smoothing techniques are implemented.
- "Streamlit UI — all specified PredictorUI methods implemented" (5 pts): Check if src/ui/app.py exists and correctly implements proper Streamlit components.
- "Exception Handling — specific exception types and informative messages" (5 pts): Check for specific try/except blocks with informative messages across the execution pipeline.
- "Logging — LOG_LEVEL from .env with appropriate log levels" (5 pts): Check if logging module is used.
- "Model Evaluator — correct perplexity computation on held-out corpus" (5 pts): Check if testing/evaluation computes perplexity accurately.

**JSON Output Format:**
```json
{
  "Code Structure": {
    "No file paths or thresholds hardcoded; all loaded from config/.env": {"score": X, "reasoning": "..."}
  },
  "General Coding": {
    "All classes and methods have docstrings (proportional)": {"score": X, "reasoning": "..."},
    "No global variables": {"score": X, "reasoning": "..."},
    "No code duplication — each piece of logic exists in exactly one place": {"score": X, "reasoning": "..."}
  },
  "Design Quality": {
    "All classes and methods specified in the instructions are implemented (proportional)": {"score": X, "reasoning": "..."},
    "NGramModel.lookup() is the single source of backoff logic — not re-implemented in any other module": {"score": X, "reasoning": "..."},
    "Normalizer.normalize() reused in Module 3 — not re-implemented": {"score": X, "reasoning": "..."},
    "Dependency injection — NGramModel and Normalizer instantiated once in main() and passed in": {"score": X, "reasoning": "..."}
  },
  "Extra Credit": {
    "Smoothing — any technique from Sections 3–6 of the reference paper": {"score": X, "reasoning": "..."},
    "Streamlit UI — all specified PredictorUI methods implemented": {"score": X, "reasoning": "..."},
    "Exception Handling — specific exception types and informative messages": {"score": X, "reasoning": "..."},
    "Logging — LOG_LEVEL from .env with appropriate log levels": {"score": X, "reasoning": "..."},
    "Model Evaluator — correct perplexity computation on held-out corpus": {"score": X, "reasoning": "..."},
  }
}
```
"""

# **AI Generation Check**
# - "AI Probability": Based on your deep expertise, analyze the code for typical AI-generation patterns (e.g., specific comment styles, perfect but generic structures, variable naming conventions typical of LLMs, lack of human-like idiosyncrasies). Provide a percentage from 0 to 100 representing how certain you are that this code was generated by an AI.
#
# ,
# "AI Detection": {
#   "AI Probability": {"percentage": X, "reasoning": "..."}
# }
