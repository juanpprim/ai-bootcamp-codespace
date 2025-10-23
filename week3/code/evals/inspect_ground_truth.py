"""
Ground Truth Inspector - Streamlit App

Interactive tool to view, edit, and curate ground truth questions.
Allows manual selection of "good" questions into a separate file.

Usage:
    uv run streamlit run evals/inspect_ground_truth.py -- --input evals/ground_truth_evidently.csv
"""

import streamlit as st
import pandas as pd
import sys
from pathlib import Path


def load_data(csv_path: str) -> pd.DataFrame:
    """Load ground truth CSV file."""
    return pd.read_csv(csv_path)


def save_data(df: pd.DataFrame, output_path: str):
    """Save dataframe to CSV."""
    df.to_csv(output_path, index=False)
    return output_path


def initialize_session_state():
    """Initialize session state variables."""
    if 'selected_indices' not in st.session_state:
        st.session_state.selected_indices = set()
    if 'edited_questions' not in st.session_state:
        st.session_state.edited_questions = {}


def main():
    st.set_page_config(page_title="Ground Truth Inspector", layout="wide")
    
    st.title("🔍 Ground Truth Inspector")
    st.markdown("View, edit, and curate ground truth questions for evaluation")
    
    initialize_session_state()
    
    # Sidebar for file operations
    st.sidebar.header("📁 File Operations")
    
    # Get input file from command line or sidebar
    if len(sys.argv) > 1 and sys.argv[1] == "--input" and len(sys.argv) > 2:
        default_input = sys.argv[2]
    else:
        default_input = "evals/ground_truth_evidently.csv"
    
    input_file = st.sidebar.text_input("Input CSV Path", value=default_input)
    
    if not Path(input_file).exists():
        st.error(f"❌ File not found: {input_file}")
        st.stop()
    
    # Load data
    df = load_data(input_file)
    
    st.sidebar.success(f"✅ Loaded {len(df)} questions")
    
    # Display dataset info
    st.sidebar.metric("Total Questions", len(df))
    st.sidebar.metric("Selected", len(st.session_state.selected_indices))
    
    # Export options
    st.sidebar.markdown("---")
    st.sidebar.subheader("💾 Export Options")
    
    output_file = st.sidebar.text_input(
        "Output CSV Path",
        value="evals/ground_truth_curated.csv"
    )
    
    if st.sidebar.button("📥 Export Selected Questions"):
        if len(st.session_state.selected_indices) == 0:
            st.sidebar.warning("⚠️ No questions selected")
        else:
            selected_df = df.loc[list(st.session_state.selected_indices)].copy()
            
            # Apply any edits
            for idx, edited_q in st.session_state.edited_questions.items():
                if idx in st.session_state.selected_indices:
                    selected_df.loc[idx, 'question'] = edited_q
            
            save_data(selected_df, output_file)
            st.sidebar.success(f"✅ Exported {len(selected_df)} questions to {output_file}")
    
    # Main content area
    col1, col2 = st.columns([1, 3])
    
    with col1:
        st.subheader("Filters")
        
        # Search filter
        search_query = st.text_input("🔎 Search in questions", "")
        
        # Filter by filename/source if available
        if 'filename' in df.columns:
            filenames = ['All'] + sorted(df['filename'].unique().tolist())
            selected_filename = st.selectbox("📄 Filter by filename", filenames)
        else:
            selected_filename = 'All'
        
        # Show only selected
        show_selected_only = st.checkbox("Show only selected")
    
    with col2:
        st.subheader("Questions")
        
        # Apply filters
        filtered_df = df.copy()
        
        if search_query:
            filtered_df = filtered_df[
                filtered_df['question'].str.contains(search_query, case=False, na=False)
            ]
        
        if selected_filename != 'All' and 'filename' in df.columns:
            filtered_df = filtered_df[filtered_df['filename'] == selected_filename]
        
        if show_selected_only:
            filtered_df = filtered_df.loc[
                filtered_df.index.isin(st.session_state.selected_indices)
            ]
        
        st.info(f"Showing {len(filtered_df)} of {len(df)} questions")
        
        # Display questions
        for idx, row in filtered_df.iterrows():
            with st.container():
                col_check, col_content = st.columns([0.5, 9.5])
                
                with col_check:
                    is_selected = idx in st.session_state.selected_indices
                    if st.checkbox("✓", value=is_selected, key=f"select_{idx}"):
                        st.session_state.selected_indices.add(idx)
                    else:
                        st.session_state.selected_indices.discard(idx)
                
                with col_content:
                    # Show index and metadata
                    metadata_parts = [f"**ID: {idx}**"]
                    if 'filename' in row:
                        metadata_parts.append(f"📄 {row['filename']}")
                    if 'section' in row:
                        metadata_parts.append(f"§ {row['section']}")
                    
                    st.markdown(" | ".join(metadata_parts))
                    
                    # Question text (editable)
                    current_question = st.session_state.edited_questions.get(idx, row['question'])
                    
                    edited_question = st.text_area(
                        "Question",
                        value=current_question,
                        key=f"question_{idx}",
                        height=100,
                        label_visibility="collapsed"
                    )
                    
                    # Track edits
                    if edited_question != row['question']:
                        st.session_state.edited_questions[idx] = edited_question
                        st.caption("✏️ *Edited*")
                    
                    # Show original if edited
                    if idx in st.session_state.edited_questions:
                        with st.expander("Show original"):
                            st.text(row['question'])
                
                st.divider()
    
    # Bulk actions
    st.sidebar.markdown("---")
    st.sidebar.subheader("⚡ Bulk Actions")
    
    col_sel, col_desel = st.sidebar.columns(2)
    
    with col_sel:
        if st.button("Select All Visible"):
            st.session_state.selected_indices.update(filtered_df.index.tolist())
            st.rerun()
    
    with col_desel:
        if st.button("Deselect All"):
            st.session_state.selected_indices.clear()
            st.rerun()


if __name__ == "__main__":
    main()
