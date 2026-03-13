import os
import sys
import json
import asyncio
import pandas as pd
from dotenv import load_dotenv

# Ensure we can import from the evals module
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from evals.llm_judge import create_log_judge_agent, format_judge_prompt

# Load environment variables (e.g., OPENAI_API_KEY)
load_dotenv()

import re

async def evaluate_sample(judge, row):
    prompt = format_judge_prompt(row)
    prompt = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', prompt)
    eval_result = await judge.run(prompt)
    return eval_result.output

async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Run LLM Judge Evaluation")
    parser.add_argument("--data", default="evals_run_2026_03_06_results.json", help="Path to results file")
    args = parser.parse_args()

    results_path = args.data
    # Use absolute path if relative is provided
    if not os.path.isabs(results_path):
        results_path = os.path.join(os.path.dirname(__file__), results_path)

    print(f"Loading data from {results_path}...")
    with open(results_path, "r") as f:
        results = json.load(f)

    print(f"Running evaluation on {len(results)} samples...")
    judge = create_log_judge_agent()

    eval_results = []
    
    # Try importing tqdm for a progress bar, fallback to simple prints if unavailable
    try:
        from tqdm.asyncio import tqdm
        iterable = tqdm(results, desc="Evaluating")
    except ImportError:
        iterable = results

    for i, row in enumerate(iterable):
        if type(iterable) is list:
            print(f"Evaluating {i+1}/{len(results)}...")
        try:
            eval_output = await evaluate_sample(judge, row)
            eval_results.append({
                'row': row,
                'label': eval_output.label,
                'reasoning': eval_output.reasoning
            })
        except Exception as e:
            print(f"\nError evaluating sample {i}: {e}")
            eval_results.append({
                'row': row,
                'label': 'bad', # Fallback to negative label if evaluation fails
                'reasoning': f"Evaluation failed with error: {str(e)}"
            })

    rows = []
    for result in eval_results:
        rows.append({
            'question': result['row']['input']['question'],
            'llm_answer': result['row']['rag_response']['answer'],
            'human_label': result['row']['label'],
            'human_comment': result['row'].get('comments', ''),
            'llm_label': result['label'],
            'llm_reasoning': result['reasoning']
        })

    df = pd.DataFrame(rows)

    print("\n" + "="*50)
    print("--- Evaluation Results ---")
    print("="*50)

    # Calculate metrics with 'bad' as the positive class
    # y_true = actual labels, y_pred = model labels
    y_true_bad = df['human_label'] == 'bad'
    y_pred_bad = df['llm_label'] == 'bad'

    tp = (y_true_bad & y_pred_bad).sum()
    fp = (~y_true_bad & y_pred_bad).sum()
    fn = (y_true_bad & ~y_pred_bad).sum()
    tn = (~y_true_bad & ~y_pred_bad).sum()

    accuracy = (tp + tn) / len(df)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0

    print(f"Total samples: {len(df)}")
    print(f"Accuracy:  {accuracy:.3f} ({accuracy * 100:.1f}%)")
    print(f"Precision (class='bad'): {precision:.3f} ({precision * 100:.1f}%)")
    print(f"Recall    (class='bad'): {recall:.3f} ({recall * 100:.1f}%)")

    print("\nConfusion Matrix:")
    print(f"                 Predicted 'good'   Predicted 'bad'")
    print(f"Actual 'good'    {tn:<19} {fp}")
    print(f"Actual 'bad'     {fn:<19} {tp}")

    # Output cases of disagreement for easy debugging
    df_disagreement = df[df['human_label'] != df['llm_label']]
    if not df_disagreement.empty:
        print("\n--- Disagreements ---")
        for idx, row in df_disagreement.iterrows():
            print(f"Q: {row['question']}")
            print(f"  Human: {row['human_label']} (Comment: {row['human_comment']})")
            print(f"  LLM:   {row['llm_label']} (Reasoning: {row['llm_reasoning'][:150]}...)")
            print("-" * 30)

    output_path = results_path.replace(".json", "_evaluated.csv")
    df.to_csv(output_path, index=False)
    print(f"\nDetailed evaluation saved to {output_path}")

if __name__ == "__main__":
    asyncio.run(main())
