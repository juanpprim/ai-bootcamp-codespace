# Evaluation System

This directory contains a modular evaluation system for the search agent.

**Important**: All commands should be run from the project root directory (`/workspaces/ai-bootcamp-codespace/week3/code`), not from within the `evals/` directory.

**Quick Start**: See [INSPECTOR_GUIDE.md](INSPECTOR_GUIDE.md) for detailed instructions on using the interactive inspection tools.

## Structure

### Core Modules

1. **`sample_ground_truth.py`** - Ground truth sampler
   - Samples questions from full dataset
   - Ensures reproducibility with random seeds
   - Saves to CSV for evaluation

2. **`eval_common.py`** - Shared utilities
   - `map_progress()` - Async progress tracking
   - `calculate_cost()` - Cost calculation returning CostInfo from toyaikit
   - `simplify_messages()` - Message formatting

3. **`eval_agent_run.py`** - Agent evaluation runner
   - Runs agent on ground truth questions
   - Saves results for judge evaluation
   - Tracks costs and performance

4. **`eval_agent_judge.py`** - Judge evaluation
   - Evaluates agent outputs using LLM judge
   - Checks quality, relevance, completeness
   - Produces evaluation metrics

5. **`eval_orchestrator.py`** - Complete pipeline
   - Orchestrates run + judge evaluation
   - Displays comprehensive reports
   - Tracks total costs

6. **`inspect_ground_truth.py`** - Ground truth inspector (Streamlit)
   - View and edit ground truth questions
   - Select good questions for curation
   - Export curated datasets

7. **`inspect_eval_results.py`** - Evaluation results inspector (Streamlit)
   - Deep dive into evaluation results
   - Filter by criteria (tool calls, answer length, etc.)
   - View detailed tool calls and message logs
   - Identify potential issues

### Directory Structure

```
week3/code/
├── evals/
│   ├── sample_ground_truth.py
│   ├── eval_common.py
│   ├── eval_agent_run.py
│   ├── eval_agent_judge.py
│   ├── eval_orchestrator.py
│   ├── ground_truth_evidently.csv  # Full dataset
│   ├── gt-sample.csv               # Your sampled datasets
│   └── README.md
└── reports/                         # Auto-created for outputs
    ├── eval-run-<timestamp>.bin     # Agent run results
    └── eval-report-<timestamp>.txt  # Detailed reports
```

## Usage

### Complete Workflow (Recommended)

**Note**: Run all commands from the project root (`/workspaces/ai-bootcamp-codespace/week3/code`)

#### Step 0: Sample Ground Truth (for reproducibility)

```bash
# Sample 25 questions with random_state=1 for reproducibility
uv run python -m evals.sample_ground_truth \
    --sample-size 25 \
    --random-state 1 \
    --input evals/ground_truth_evidently.csv \
    --output evals/gt-sample.csv

# Sample with specific extra indices
uv run python -m evals.sample_ground_truth \
    --sample-size 25 \
    --extra-indices 150 200 \
    --input evals/ground_truth_evidently.csv \
    --output evals/gt-sample.csv

# Use all questions (no sampling)
uv run python -m evals.sample_ground_truth \
    --input evals/ground_truth_evidently.csv \
    --output evals/gt-all.csv

# Save to specific file with custom size
uv run python -m evals.sample_ground_truth \
    --sample-size 50 \
    --input evals/ground_truth_evidently.csv \
    --output evals/gt-sample-50.csv
```

This creates a CSV file that you can use for reproducible evaluations.

#### Step 1+2: Run Complete Evaluation Pipeline

```bash
# Run with sampled dataset
uv run python -m evals.eval_orchestrator --csv evals/gt-sample.csv

# Run with full dataset
uv run python -m evals.eval_orchestrator --csv evals/ground_truth_evidently.csv

# Custom configuration
uv run python -m evals.eval_orchestrator \
    --csv evals/gt-sample.csv \
    --agent-model gpt-4o-mini \
    --judge-model gpt-5-nano \
    --concurrency 10
```

### Run Individual Steps

#### Step 1: Run Agent Evaluation

```bash
# Use sampled dataset
uv run python -m evals.eval_agent_run --csv evals/gt-sample.csv

# Or use full dataset
uv run python -m evals.eval_agent_run --csv evals/ground_truth_evidently.csv

# With custom settings
uv run python -m evals.eval_agent_run \
    --csv evals/gt-sample.csv \
    --model gpt-4o-mini \
    --concurrency 10
```

This will:
- Load ground truth questions from CSV
- Run the agent on each question
- Save results to `reports/eval-run-<timestamp>.bin`
- Display cost breakdown

#### Step 2: Run Judge Evaluation

```bash
uv run python -m evals.eval_agent_judge reports/eval-run-<timestamp>.bin
```

This will:
- Load agent run results
- Evaluate each result with judge
- Display evaluation metrics
- Show cost breakdown

### Use as Library

```python
import asyncio
from evals.sample_ground_truth import sample_ground_truth
from evals.eval_orchestrator import run_full_evaluation

# First, create a reproducible sample
sample_path = sample_ground_truth(
    csv_path='evals/ground_truth_evidently.csv',
    sample_size=25,
    random_state=1,
    extra_indices=[150],
    output_path='evals/gt-sample.csv'
)

# Run complete pipeline
results = asyncio.run(run_full_evaluation(
    csv_path=sample_path,
    agent_model='gpt-4o-mini',
    judge_model='gpt-5-nano',
    max_concurrency=10
))

# Access results
print(f"Total cost: ${results['total_cost'].total_cost:.4f}")
print(f"Overall score: {results['metrics'].mean():.1%}")
```

Or use individual components:

```python
from evals.eval_agent_run import run_agent_evaluation
from evals.eval_agent_judge import run_complete_judge_evaluation

# Run agent evaluation on pre-sampled dataset
saved_path, run_cost, df_run = await run_agent_evaluation(
    csv_path='evals/gt-sample.csv',
    model='gpt-4o-mini'
)

# Run judge evaluation
judge_cost, df_eval, metrics = await run_complete_judge_evaluation(
    input_path=saved_path,
    model='gpt-5-nano'
)
```

## Output

### Console Output

The orchestrator provides:
- Real-time progress tracking
- Cost breakdowns per step
- Evaluation metrics with visual indicators
- Total costs and duration

### Files Generated

1. **`reports/eval-run-<timestamp>.bin`** - Agent run results (pickle format)
2. **`reports/eval-report-<timestamp>.txt`** - Detailed text report

All reports are automatically saved to the `reports/` directory in the project root.

### Evaluation Metrics

The judge evaluates on these dimensions:
- `instructions_follow` - Followed instructions
- `instructions_avoid` - Avoided prohibited actions
- `answer_relevant` - Relevance to question
- `answer_clear` - Clarity and correctness
- `answer_citations` - Proper citations
- `completeness` - Complete answer
- `tool_call_search` - Search tool usage

## Cost Tracking

The system uses the `CostInfo` dataclass:

```python
@dataclass
class CostInfo:
    input_cost: float      # Cost for input tokens
    output_cost: float     # Cost for output tokens
    total_cost: float      # Total cost
```

Costs are tracked separately for:
- Agent run (using agent model, e.g., gpt-4o-mini)
- Judge evaluation (using judge model, e.g., gpt-5-nano)
- Total pipeline cost (sum of both)

## Refactoring Benefits

✅ **No global variables** - All state passed as function parameters
✅ **Modular functions** - Each function has single responsibility
✅ **Reusable utilities** - Common code in eval_common.py
✅ **Importable** - Can be used as library or CLI
✅ **Type hints** - Better IDE support and documentation
✅ **Error handling** - Graceful error handling throughout
✅ **Progress tracking** - Visual feedback during execution
✅ **Comprehensive reports** - Detailed cost and metric tracking
✅ **Reproducibility** - Separate sampling step ensures consistent evaluations
✅ **Flexibility** - Point to any CSV file for evaluation

## Examples

### Complete Workflow with Inspection

```bash
# 1. Inspect and curate ground truth
uv run streamlit run evals/inspect_ground_truth.py -- --input evals/ground_truth_evidently.csv
# Select good questions and export to evals/gt-curated.csv

# 2. Create evaluation sample
uv run python -m evals.sample_ground_truth \
    --sample-size 25 \
    --input evals/gt-curated.csv \
    --output evals/gt-sample.csv

# 3. Run evaluation
uv run python -m evals.eval_orchestrator --csv evals/gt-sample.csv

# 4. Inspect results
uv run streamlit run evals/inspect_eval_results.py
# Review results, identify issues, filter by criteria
```

### Quick Test (5 samples)

```bash
# Step 1: Create sample
uv run python -m evals.sample_ground_truth \
    --sample-size 5 \
    --input evals/ground_truth_evidently.csv \
    --output evals/gt-test.csv

# Step 2: Run evaluation
uv run python -m evals.eval_orchestrator --csv evals/gt-test.csv

# Step 3: Inspect results
uv run streamlit run evals/inspect_eval_results.py
```

### Full Evaluation

```bash
# Use full dataset directly
uv run python -m evals.eval_orchestrator --csv evals/ground_truth_evidently.csv
```

### Reproducible Evaluation

```bash
# Create reproducible sample with fixed random seed
uv run python -m evals.sample_ground_truth \
    --sample-size 25 \
    --random-state 42 \
    --input evals/ground_truth_evidently.csv \
    --output evals/gt-eval-v1.csv

# Run evaluation (can be repeated with same results)
uv run python -m evals.eval_orchestrator --csv evals/gt-eval-v1.csv
```

### Custom Models

```bash
uv run python -m evals.eval_orchestrator \
    --csv evals/gt-sample.csv \
    --agent-model gpt-4o \
    --judge-model gpt-4o-mini
```

## Interactive Inspector Tools

### Ground Truth Inspector

Interactive Streamlit app to view, edit, and curate ground truth questions.

```bash
# Launch the inspector
uv run streamlit run evals/inspect_ground_truth.py -- --input evals/ground_truth_evidently.csv
```

**Features:**
- 📋 View all ground truth questions
- ✏️ Edit questions inline
- ✓ Select "good" questions for curation
- 🔍 Search and filter questions
- 💾 Export curated dataset to new CSV
- ⚡ Bulk select/deselect operations

**Workflow:**
1. Load your ground truth CSV
2. Browse and review questions
3. Edit any questions that need improvement
4. Check the boxes next to good questions
5. Export selected questions to a new file

### Evaluation Results Inspector

Interactive Streamlit app to deep dive into evaluation results.

```bash
# Launch the inspector (auto-detects latest results)
uv run streamlit run evals/inspect_eval_results.py

# Or specify a results file
uv run streamlit run evals/inspect_eval_results.py -- --input reports/eval-run-2025-10-23-12-00.bin
```

**Features:**
- 📊 Summary metrics (avg tool calls, answer length, etc.)
- 🔍 Filter by tool call count, answer length, search terms
- 🛠️ View detailed tool calls and arguments
- 📜 Inspect full message logs
- ⚠️ Identify potential issues (too many/few tool calls, short/long answers)
- 📃 List and detailed views
- 💾 Export filtered results to CSV

**Use Cases:**
- Find results with excessive tool calls
- Identify answers that are too short or too long
- Debug specific questions
- Review tool usage patterns
- Export problematic cases for further analysis

## Dependencies

- pandas
- pydantic
- pydantic_ai
- toyaikit
- tqdm
- streamlit
- asyncio (stdlib)
