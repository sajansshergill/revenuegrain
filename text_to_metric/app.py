"""
Minimal Streamlit front-end for the text-to-metric layer.

    streamlit run text_to_metric/app.py

CLI (no Streamlit):

    python -m text_to_metric "What was NRR by month in 2025?"
"""
from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from text_to_metric.query_builder import QueryBuilder, load_semantic_layer

import streamlit as st

st.set_page_config(page_title="RevenueGrain — Ask a Metric", page_icon="📊")
st.title("RevenueGrain — Ask a Metric")
st.caption("Natural-language questions, answered against governed, tested metrics.")

semantic = load_semantic_layer()
with st.expander("Available metrics"):
    for m in semantic["metrics"]:
        st.markdown(f"- **{m['label']}** (`{m['name']}`) — {m['description']}")

if not os.environ.get("ANTHROPIC_API_KEY"):
    st.warning("No ANTHROPIC_API_KEY set — generating SQL from the semantic layer locally.")

question = st.text_input(
    "Ask a question",
    placeholder="What was net revenue retention by month in 2025?",
)

if st.button("Generate SQL") and question:
    with st.spinner("Generating SQL..."):
        try:
            builder = QueryBuilder(semantic=semantic)
            sql = builder.build(question)
        except Exception as exc:
            st.error(str(exc))
        else:
            st.code(sql, language="sql")
            if builder.used_llm:
                st.info("Generated with Claude against the governed semantic layer.")
            else:
                st.info("Compiled locally from semantic_layer.yml. Review before running.")
