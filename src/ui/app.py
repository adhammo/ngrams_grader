import sys
import os
from pathlib import Path
import streamlit as st

# Ensure the project root is on sys.path so src.* imports work when Streamlit
# launches this file directly (e.g. `streamlit run src/ui/app.py`).
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.grader.engine import GraderEngine
from src.rubric.rubric import RUBRIC_STRUCTURE, LLM_GRADED_CRITERIA

st.set_page_config(page_title="N-Gram Grader", page_icon="🎓", layout="wide")

st.markdown(
    """
    <style>
    /* Only target full code blocks (pre-wrapped) to keep inline codes default */
    pre, pre *, pre code {
        color: #2a2018 !important;
        font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace !important;
        text-shadow: none !important;
    }
    
    /* Base typography overrides */
    html, body, [class*="css"] {
        font-family: Georgia, "Times New Roman", serif !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🎓 N-Gram Next-Word Predictor Auto-Grader")
st.markdown("Automated AI grading system for the ADI Egypt N-Gram Capstone Project.")

st.sidebar.header("Configuration")
repo_url = st.sidebar.text_input(
    "GitHub Repository URL",
    placeholder="https://github.com/username/ngram-predictor",
    value="https://github.com/adhammo/ngrams",
)
api_key = st.sidebar.text_input(
    "Gemini API Key",
    value=os.getenv("GEMINI_KEY", ""),
    type="password",
    help="Required for Design Quality and General Coding evaluation.",
)

if st.sidebar.button("Run Grader", type="primary"):
    if not repo_url:
        st.sidebar.error("Please provide a GitHub Repository URL.")
    else:
        st.write("### Grading Progress")

        with st.spinner("Grading in progress... this may take a minute or two."):
            log_container = st.empty()
            logs = []

            def ui_log_callback(message, level=0):
                indent = "  " * level
                if level == 2:
                    indent += "- "
                logs.append(f"{indent}{message}")
                log_container.code("\n".join(logs), language=None)

            engine = GraderEngine(
                repo_url=repo_url,
                api_key=api_key if api_key else None,
                log_callback=ui_log_callback,
            )
            scores, reasoning, ai_detection, llm_success = engine.run_tests()

            st.success("Grading Complete!")

            st.write("---")
            st.write("## 🏆 Final Grade Report")

            total_score = 0
            total_max = 0
            for category, criteria in scores.items():
                for crit, val in criteria.items():
                    # Determine if LLM-based grading was successful for this criterion
                    include_score = (crit not in LLM_GRADED_CRITERIA) or llm_success

                    if include_score:
                        total_score += val
                        # Only include in the denominator if it's NOT Extra Credit
                        if category != "Extra Credit":
                            total_max += RUBRIC_STRUCTURE[category][crit]

            metric_label = "Total Score"
            if total_score > (0.75 * total_max):
                metric_label += " (:green[PASS])"
            else:
                metric_label += " (:red[FAIL])"

            reason_msg = reasoning.get("Project", {}).get(
                "runs end-to-end without errors (python main.py --step all)", ""
            )

            st.metric(metric_label, f"{total_score} / {total_max}")

            if not llm_success:
                st.warning(
                    "⚠️ **LLM Evaluation Unavailable**: AI-based criteria (General Coding, Design Quality, etc.) have been excluded from the total score calculation."
                )

            if False and ai_detection and "AI Probability" in ai_detection:
                prob = ai_detection["AI Probability"].get("percentage", 0)
                reason = ai_detection["AI Probability"].get(
                    "reasoning", "No specific reasoning provided."
                )
                if prob > 50:
                    st.error(
                        f"**🤖 AI Generation Probability: {prob}%**\n\n*Reasoning*: {reason}"
                    )
                elif prob > 20:
                    st.warning(
                        f"**🤖 AI Generation Probability: {prob}%**\n\n*Reasoning*: {reason}"
                    )
                else:
                    st.info(
                        f"**🤖 AI Generation Probability: {prob}%**\n\n*Reasoning*: {reason}"
                    )

            for category, criteria in scores.items():
                st.subheader(f"{category}")
                cat_total = sum(criteria.values())
                cat_max = sum(RUBRIC_STRUCTURE.get(category, {}).values())
                st.write(f"**Category Total: {cat_total} / {cat_max}**")

                for crit, val in criteria.items():
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.markdown(f"- {crit}")
                    with col2:
                        max_val = RUBRIC_STRUCTURE.get(category, {}).get(crit, 0)

                        # Determine if this specific criterion was skipped
                        is_skipped = not llm_success and crit in LLM_GRADED_CRITERIA
                        pts_display = f"**{val} / {max_val} pts**"

                        if is_skipped:
                            st.markdown(
                                f"{pts_display} &nbsp;&nbsp; :orange[(SKIPPED)]"
                            )
                        elif (
                            crit
                            == "runs end-to-end without errors (python main.py --step all)"
                        ):
                            reason_msg = reasoning.get(category, {}).get(crit, "")
                            if reason_msg and "woman" in reason_msg.lower():
                                st.markdown(
                                    f"{pts_display} &nbsp;&nbsp; :green[+ correct answer]"
                                )
                            else:
                                st.markdown(pts_display)
                        else:
                            st.markdown(pts_display)
                    if crit in reasoning[category] and reasoning[category][crit]:
                        st.info(f"Reasoning: {reasoning[category][crit]}")
                st.write("")
