"""
Evaluation Results Inspector - Streamlit App

Interactive tool to inspect evaluation results in depth.
View reports, filter by criteria, inspect tool calls, and identify issues.

Usage:
    uv run streamlit run evals/inspect_eval_results.py -- --input reports/eval-run-2025-10-23-12-00.bin
"""

import streamlit as st
import pandas as pd
import pickle
import json
import sys
from pathlib import Path
from typing import Optional


def load_eval_results(bin_path: str) -> list[dict]:
    """Load evaluation results from pickle file."""
    with open(bin_path, 'rb') as f_in:
        return pickle.load(f_in)


def load_judge_results(bin_path: str) -> Optional[list]:
    """Try to load judge results if available."""
    # Try to find matching judge results
    judge_path = bin_path.replace('eval-run-', 'eval-judge-')
    if Path(judge_path).exists():
        with open(judge_path, 'rb') as f_in:
            return pickle.load(f_in)
    return None


def extract_tool_calls(messages: list[dict]) -> list[dict]:
    """Extract tool calls from messages."""
    tool_calls = []
    for msg in messages:
        if msg.get('kind') == 'tool-call':
            tool_calls.append({
                'tool_name': msg.get('tool_name'),
                'args': msg.get('args', {})
            })
    return tool_calls


def count_tool_calls(messages: list[dict]) -> int:
    """Count total tool calls."""
    return sum(1 for msg in messages if msg.get('kind') == 'tool-call')


def initialize_session_state():
    """Initialize session state variables."""
    if 'expanded_results' not in st.session_state:
        st.session_state.expanded_results = set()


def format_tool_call(tool_call: dict) -> str:
    """Format a tool call for display."""
    tool_name = tool_call.get('tool_name', 'unknown')
    args = tool_call.get('args', {})
    
    if isinstance(args, dict):
        args_str = json.dumps(args, indent=2)
    else:
        args_str = str(args)
    
    return f"**{tool_name}**\n```json\n{args_str}\n```"


def main():
    st.set_page_config(page_title="Evaluation Results Inspector", layout="wide")
    
    st.title("🔬 Evaluation Results Inspector")
    st.markdown("Deep dive into agent evaluation results with filtering and detailed inspection")
    
    initialize_session_state()
    
    # Sidebar for file and filter operations
    st.sidebar.header("📁 Load Results")
    
    # Get input file from command line or sidebar
    if len(sys.argv) > 1 and sys.argv[1] == "--input" and len(sys.argv) > 2:
        default_input = sys.argv[2]
    else:
        # Try to find the most recent eval-run file
        reports_dir = Path("reports")
        if reports_dir.exists():
            eval_files = sorted(reports_dir.glob("eval-run-*.bin"), reverse=True)
            default_input = str(eval_files[0]) if eval_files else "reports/eval-run-latest.bin"
        else:
            default_input = "reports/eval-run-latest.bin"
    
    input_file = st.sidebar.text_input("Results File (.bin)", value=default_input)
    
    if not Path(input_file).exists():
        st.error(f"❌ File not found: {input_file}")
        st.info("💡 Run an evaluation first:\n```bash\nuv run python -m evals.eval_orchestrator --csv evals/gt-sample.csv\n```")
        st.stop()
    
    # Load data
    results = load_eval_results(input_file)
    df = pd.DataFrame(results)
    
    # Add computed columns
    df['tool_call_count'] = df['messages'].apply(count_tool_calls)
    df['answer_length'] = df['answer'].str.len()
    
    st.sidebar.success(f"✅ Loaded {len(df)} results")
    
    # Summary metrics
    st.sidebar.header("📊 Summary Metrics")
    st.sidebar.metric("Total Questions", len(df))
    st.sidebar.metric("Avg Tool Calls", f"{df['tool_call_count'].mean():.1f}")
    st.sidebar.metric("Avg Answer Length", f"{df['answer_length'].mean():.0f} chars")
    
    # Filters
    st.sidebar.header("🔍 Filters")
    
    # Tool call range filter
    min_tools, max_tools = st.sidebar.slider(
        "Tool Calls Range",
        min_value=0,
        max_value=int(df['tool_call_count'].max()),
        value=(0, int(df['tool_call_count'].max()))
    )
    
    # Answer length filter
    min_length, max_length = st.sidebar.slider(
        "Answer Length Range",
        min_value=0,
        max_value=int(df['answer_length'].max()),
        value=(0, int(df['answer_length'].max()))
    )
    
    # Search filter
    search_query = st.sidebar.text_input("🔎 Search in questions/answers", "")
    
    # Show only issues
    show_issues_only = st.sidebar.checkbox("Show only potential issues")
    
    # Apply filters
    filtered_df = df.copy()
    
    filtered_df = filtered_df[
        (filtered_df['tool_call_count'] >= min_tools) &
        (filtered_df['tool_call_count'] <= max_tools) &
        (filtered_df['answer_length'] >= min_length) &
        (filtered_df['answer_length'] <= max_length)
    ]
    
    if search_query:
        filtered_df = filtered_df[
            filtered_df['question'].str.contains(search_query, case=False, na=False) |
            filtered_df['answer'].str.contains(search_query, case=False, na=False)
        ]
    
    if show_issues_only:
        # Define "issues" as too many or too few tool calls, or very short/long answers
        filtered_df = filtered_df[
            (filtered_df['tool_call_count'] > 10) |
            (filtered_df['tool_call_count'] < 2) |
            (filtered_df['answer_length'] < 100) |
            (filtered_df['answer_length'] > 2000)
        ]
    
    # Main content
    st.info(f"📋 Showing {len(filtered_df)} of {len(df)} results")
    
    # Tabs for different views
    tab_list, tab_details = st.tabs(["📃 List View", "🔎 Detailed View"])
    
    with tab_list:
        # Quick overview table
        display_df = filtered_df[['question', 'tool_call_count', 'answer_length']].copy()
        display_df['question_preview'] = display_df['question'].str[:100] + '...'
        
        st.dataframe(
            display_df[['question_preview', 'tool_call_count', 'answer_length']],
            use_container_width=True,
            height=600
        )
    
    with tab_details:
        # Sort options
        sort_by = st.selectbox(
            "Sort by",
            ["Index", "Tool Calls (High to Low)", "Tool Calls (Low to High)", 
             "Answer Length (Long to Short)", "Answer Length (Short to Long)"]
        )
        
        if sort_by == "Tool Calls (High to Low)":
            filtered_df = filtered_df.sort_values('tool_call_count', ascending=False)
        elif sort_by == "Tool Calls (Low to High)":
            filtered_df = filtered_df.sort_values('tool_call_count', ascending=True)
        elif sort_by == "Answer Length (Long to Short)":
            filtered_df = filtered_df.sort_values('answer_length', ascending=False)
        elif sort_by == "Answer Length (Short to Long)":
            filtered_df = filtered_df.sort_values('answer_length', ascending=True)
        
        # Display detailed results
        for idx, row in filtered_df.iterrows():
            with st.container():
                # Header with metrics
                col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                
                with col1:
                    st.markdown(f"### 📝 Result #{idx}")
                
                with col2:
                    st.metric("Tool Calls", row['tool_call_count'])
                
                with col3:
                    st.metric("Requests", row.get('requests', 'N/A'))
                
                with col4:
                    st.metric("Answer Length", row['answer_length'])
                
                # Question
                with st.expander("❓ Question", expanded=True):
                    st.markdown(row['question'])
                    
                    # Show original question metadata if available
                    if 'original_question' in row and isinstance(row['original_question'], dict):
                        orig = row['original_question']
                        if 'filename' in orig:
                            st.caption(f"📄 Source: {orig['filename']}")
                        if 'section' in orig:
                            st.caption(f"§ Section: {orig['section']}")
                
                # Answer
                with st.expander("💬 Answer", expanded=False):
                    st.markdown(row['answer'])
                
                # Tool Calls
                with st.expander(f"🛠️ Tool Calls ({row['tool_call_count']})", expanded=False):
                    tool_calls = extract_tool_calls(row['messages'])
                    
                    if not tool_calls:
                        st.info("No tool calls found")
                    else:
                        for i, tc in enumerate(tool_calls, 1):
                            st.markdown(f"**Call #{i}**")
                            st.markdown(format_tool_call(tc))
                            if i < len(tool_calls):
                                st.divider()
                
                # Full Message Log
                with st.expander("📜 Full Message Log", expanded=False):
                    st.json(row['messages'])
                
                # Flags for potential issues
                issues = []
                if row['tool_call_count'] > 10:
                    issues.append("⚠️ High number of tool calls")
                if row['tool_call_count'] < 2:
                    issues.append("⚠️ Very few tool calls")
                if row['answer_length'] < 100:
                    issues.append("⚠️ Very short answer")
                if row['answer_length'] > 2000:
                    issues.append("⚠️ Very long answer")
                
                if issues:
                    st.warning(" | ".join(issues))
                
                st.divider()
    
    # Export options
    st.sidebar.markdown("---")
    st.sidebar.subheader("💾 Export")
    
    if st.sidebar.button("📥 Export Filtered Results to CSV"):
        export_df = filtered_df[['question', 'answer', 'tool_call_count', 'answer_length']].copy()
        export_path = "reports/filtered_results.csv"
        export_df.to_csv(export_path, index=True)
        st.sidebar.success(f"✅ Exported to {export_path}")


if __name__ == "__main__":
    main()
