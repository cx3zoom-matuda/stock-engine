import streamlit as st
import pathlib

st.set_page_config(
    page_title="Macro Engine - README / 説明書",
    page_icon="📖",
    layout="wide"
)

# Custom styling for premium look and feel
st.markdown("""
<style>
    .reportview-container {
        background: #0f172a;
    }
    .documentation-title {
        color: #38bdf8;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

st.title("📖 ドキュメント / 説明書")

# Select between Macro Engine and Stock Engine
doc_type = st.radio(
    "表示する説明書を選択してください / Select Document:",
    ["マクロ評価スクリーニングエンジン (Macro Engine)", "マクロ→産業翻訳エンジン (Stock Engine)"]
)

# Load selected markdown
current_dir = pathlib.Path(__file__).parent.parent
if "Macro Engine" in doc_type:
    readme_path = current_dir / "macro-engine" / "README.md"
else:
    readme_path = current_dir / "README.md"

if readme_path.exists():
    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Render markdown content
    st.markdown(content)
else:
    st.error("説明書ファイルが見つかりません。")
