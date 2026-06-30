"""
Streamlit Frontend — Multi-Source Candidate Data Transformer
"""

import sys
import os
import json
import tempfile

import streamlit as st

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from src.pipeline import process_candidate   # noqa: E402
import io


def _save_temp(uploaded_file, suffix):
    """Save a Streamlit UploadedFile to a real temp file and return the path."""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(uploaded_file.getbuffer())
    tmp.flush()
    tmp.close()
    return tmp.name

# ─────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Candidate Data Transformer",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─────────────────────────────────────────────
# Custom CSS — typography + hero only
# ─────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    .hero {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        border-radius: 16px;
        padding: 2.2rem 2.5rem 1.8rem 2.5rem;
        color: white;
        margin-bottom: 1.8rem;
    }
    .hero h1 { font-size: 1.9rem; font-weight: 700; margin: 0 0 .4rem 0; }
    .hero p  { font-size: .95rem; opacity: .75; margin: 0; }

    .section-label {
        font-size: .78rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: .08em;
        color: #5c6bc0;
        margin-bottom: .1rem;
    }

    div[data-testid="stButton"] > button {
        background: linear-gradient(135deg, #5c6bc0, #3949ab);
        color: white;
        border: none;
        border-radius: 10px;
        font-weight: 600;
        font-size: 1rem;
        padding: .7rem 2rem;
        width: 100%;
        transition: opacity .2s;
    }
    div[data-testid="stButton"] > button:hover { opacity: .85; }

    .metric-row { display:flex; gap:1rem; margin-bottom:1.2rem; flex-wrap:wrap; }
    .metric-box {
        background:white; border:1.5px solid #e0e0e0; border-radius:10px;
        padding:.9rem 1.4rem; flex:1; min-width:130px; text-align:center;
    }
    .metric-box .val { font-size:1.6rem; font-weight:700; color:#3949ab; }
    .metric-box .lbl { font-size:.75rem; color:#757575; margin-top:2px; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# Hero
# ─────────────────────────────────────────────
st.markdown("""
<div class="hero">
  <h1>🧠 Multi-Source Candidate Transformer</h1>
  <p>Upload structured &amp; unstructured candidate data from any source.
     The backend normalises, merges, scores, and produces one clean canonical profile.</p>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# INPUT SECTIONS
# ─────────────────────────────────────────────
col_left, col_right = st.columns([1, 1], gap="large")

# ── LEFT COLUMN — Structured Sources ──────────
with col_left:
    with st.container(border=True):
        st.markdown('<p class="section-label">📊 Structured Sources — CSV &amp; JSON</p>', unsafe_allow_html=True)
        st.caption("Recruiter spreadsheets (CSV) or ATS exports (JSON). You may upload more than one of each.")
        csv_files = st.file_uploader(
            "Recruiter CSV file(s)",
            type=["csv"],
            accept_multiple_files=True,
            key="csv_upload",
        )
        json_files = st.file_uploader(
            "ATS / Structured JSON file(s)",
            type=["json"],
            accept_multiple_files=True,
            key="json_upload",
        )

# ── RIGHT COLUMN — Unstructured Sources + GitHub ──
with col_right:
    with st.container(border=True):
        st.markdown('<p class="section-label">📄 Unstructured Sources — Resume / Notes &amp; GitHub</p>', unsafe_allow_html=True)
        st.caption("Upload resumes or recruiter notes, and optionally provide a GitHub username.")

        resume_files = st.file_uploader(
            "Resume PDF / DOCX / TXT file(s)",
            type=["pdf", "docx", "txt"],
            accept_multiple_files=True,
            key="resume_upload",
        )
        github_input = st.text_input(
            "GitHub username or URL",
            placeholder="samyamalik   or   https://github.com/samyamalik",
        )

# ── CENTRE ROW — Custom Config ────────────────
_, cfg_col, _ = st.columns([1, 2, 1])
with cfg_col:
    with st.container(border=True):
        st.markdown('<p class="section-label">⚙️ Custom Output Config (optional)</p>', unsafe_allow_html=True)
        st.caption("Upload a JSON config to control which fields appear in the output and how they are labelled.")
        config_file = st.file_uploader(
            "Output config JSON",
            type=["json"],
            accept_multiple_files=False,
            key="config_upload",
        )
        with st.expander("📋 View config format reference"):
            st.code("""{
  "fields": [
    { "path": "full_name",     "type": "string",   "required": true },
    { "path": "primary_email", "from": "emails[0]","type": "string" },
    { "path": "phone",         "from": "phones[0]","type": "string", "normalize": "E164" },
    { "path": "skills",    "from": "skills[].name", "type": "string[]" }
  ],
  "include_confidence": true,
  "include_provenance": false,
  "on_missing": "null"
}""", language="json")

# ─────────────────────────────────────────────
# RUN BUTTON
# ─────────────────────────────────────────────
st.markdown("---")
btn_col, _ = st.columns([1, 2])
with btn_col:
    run_clicked = st.button("🚀  Run Pipeline", use_container_width=True)

# ─────────────────────────────────────────────
# PIPELINE EXECUTION
# ─────────────────────────────────────────────
if run_clicked:
    sources  = {}
    tmp_files = []

    has_any = csv_files or json_files or resume_files or (github_input and github_input.strip())
    if not has_any:
        st.warning("⚠️  Please provide at least one data source before running the pipeline.")
        st.stop()

    with st.spinner("Running pipeline… fetching sources and merging records."):

        # CSVs
        for i, f in enumerate(csv_files or []):
            key = "recruiter_csv" if i == 0 else f"recruiter_csv_{i}"
            path = _save_temp(f, ".csv")
            sources[key] = path
            tmp_files.append(path)

        # JSONs
        for i, f in enumerate(json_files or []):
            key = "ats_json" if i == 0 else f"ats_json_{i}"
            path = _save_temp(f, ".json")
            sources[key] = path
            tmp_files.append(path)

        # Resumes — auto-detect type by extension
        for i, f in enumerate(resume_files or []):
            ext = os.path.splitext(f.name)[-1].lower()
            if ext == ".pdf":
                key = "resume_pdf" if "resume_pdf" not in sources else f"resume_pdf_{i}"
            elif ext == ".docx":
                key = "resume_docx" if "resume_docx" not in sources else f"resume_docx_{i}"
            else:
                key = "recruiter_notes" if "recruiter_notes" not in sources else f"recruiter_notes_{i}"
            path = _save_temp(f, ext)
            sources[key] = path
            tmp_files.append(path)

        # GitHub — extract username from full URL if provided
        if github_input and github_input.strip():
            gh = github_input.strip().rstrip("/").split("/")[-1]
            sources["github_profile"] = gh

        # Custom config — use getvalue() so the file pointer is always at start
        output_config = None
        if config_file:
            try:
                output_config = json.loads(config_file.getvalue().decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                st.error("❌ The config file is not valid JSON. Please check it and try again.")
                st.stop()

        # Run
        try:
            result = process_candidate(sources=sources, output_config=output_config)
        except Exception as exc:
            st.error(f"❌ Pipeline crashed: {exc}")
            st.stop()
        finally:
            for f in tmp_files:
                try:
                    os.unlink(f)
                except OSError:
                    pass

    # ─────────────────────────────────────────
    # RESULTS
    # ─────────────────────────────────────────
    st.markdown("## 📋 Pipeline Result")

    output       = result.get("output") or {}
    errors       = result.get("errors") or []
    is_valid     = result.get("is_valid", False)
    candidate_id = result.get("candidate_id", "—")

    warnings  = [e for e in errors if e.get("severity") == "warning"]
    hard_errs = [e for e in errors if e.get("severity") == "error"]

    # Metric summary
    st.markdown(f"""
    <div class="metric-row">
      <div class="metric-box">
        <div class="val">{"✅" if is_valid else "❌"}</div>
        <div class="lbl">Valid</div>
      </div>
      <div class="metric-box">
        <div class="val">{len(output)}</div>
        <div class="lbl">Fields Projected</div>
      </div>
      <div class="metric-box">
        <div class="val">{len(hard_errs)}</div>
        <div class="lbl">Errors</div>
      </div>
      <div class="metric-box">
        <div class="val">{len(warnings)}</div>
        <div class="lbl">Warnings</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.caption(f"**Candidate ID:** `{candidate_id}`")

    res_col, err_col = st.columns([3, 2], gap="large")

    with res_col:
        with st.container(border=True):
            st.markdown("#### Output Profile")
            if output:
                st.json(output, expanded=True)
                st.download_button(
                    label="⬇️  Download JSON",
                    data=json.dumps(
                        {"candidate_id": candidate_id, "output": output},
                        indent=2,
                        default=str,
                    ),
                    file_name=f"candidate_{candidate_id[:8]}.json",
                    mime="application/json",
                )
            else:
                st.warning("No output was produced by the pipeline.")

    with err_col:
        if hard_errs:
            with st.container(border=True):
                st.markdown("#### ❌ Errors")
                for e in hard_errs:
                    with st.expander(f"🔴 [{e.get('source','—')}] {e.get('message','')[:55]}"):
                        st.json(e)

        if warnings:
            with st.container(border=True):
                st.markdown("#### ⚠️ Warnings")
                for w in warnings:
                    with st.expander(f"🟡 [{w.get('source','—')}] {w.get('message','')[:55]}"):
                        st.json(w)

        if not errors:
            st.success("✅ No errors or warnings — clean run!")

        with st.expander("🗂️  Sources used in this run"):
            for k, v in sources.items():
                st.write(f"**{k}** → `{v}`")
