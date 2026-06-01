import os
import streamlit as st

st.set_page_config(
    page_title="Readme / G20 Macro Hub",
    page_icon="📖",
    layout="wide"
)

# Hide sidebar completely for clean single column view
st.markdown("""
    <style>
        [data-testid="stSidebar"] {
            display: none !important;
        }
        .reportview-container .main .block-container {
            max-width: 900px !important;
            padding-top: 2rem !important;
        }
    </style>
""", unsafe_allow_html=True)

# Link back to the main app
st.markdown("### [◀ Back to Screener Hub / メインアプリに戻る](https://macro-stock-engine.streamlit.app/)")
st.markdown("---")

# Resolve path to README.md in parent folder
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
readme_path = os.path.join(base_dir, "README.md")

try:
    with open(readme_path, "r", encoding="utf-8") as f:
        readme_text = f.read()
    st.markdown(readme_text)
except Exception as e:
    st.error(f"Could not load README.md: {e}")
