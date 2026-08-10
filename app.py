"""AISHA Dialogue workspace for the fictional educational onboarding demo."""

from __future__ import annotations

from datetime import date

import streamlit as st

from stai.handbook import build_handbook
from stai.models import ApplicabilityStatus
from stai.retriever import load_page_records
from stai.service import AishaService
from stai.state import Repo


DEMO_DATE = date(2026, 8, 10)
DISCLAIMER = (
    "AISHA is a fictional educational capstone prototype. It is not affiliated "
    "with, endorsed by, or representative of BDO Unibank."
)

CSS = """
<style>
:root { --navy:#12345b; --blue:#1d5fa7; --ink:#17202a; --soft:#f4f7fb; }
.stApp { color:var(--ink); }
.aisha-hero { background:linear-gradient(120deg,var(--navy),var(--blue)); color:white;
  padding:1.2rem 1.35rem; border-radius:1rem; margin-bottom:1rem; }
.aisha-hero h1 { margin:0; font-size:clamp(1.6rem,5vw,2.4rem); }
.context-card { border:1px solid #d9e2ef; background:var(--soft); padding:.8rem;
  border-radius:.75rem; margin-bottom:.6rem; }
.privacy-note { border-left:4px solid var(--blue); padding:.6rem .8rem; background:#eef5fc; }
[data-testid="stAppViewContainer"] button,
[data-testid="stFileUploaderDropzone"] { min-height: 44px !important; }
*:focus-visible { outline:3px solid #ffbf47 !important; outline-offset:2px; }
@media (max-width: 480px) {
  .block-container { padding-left:.75rem; padding-right:.75rem; }
  .aisha-hero { padding:1rem; border-radius:.65rem; }
  [data-testid="stHorizontalBlock"] { flex-wrap:wrap; }
  .stButton button { width:100%; }
}
</style>
"""


@st.cache_resource
def get_repo() -> Repo:
    return Repo()


@st.cache_resource
def get_service() -> AishaService:
    artifacts = build_handbook()
    return AishaService(get_repo(), load_page_records(artifacts.rag_pages_path))


def announce(message: str) -> None:
    st.markdown(
        f'<div role="status" aria-live="polite" class="privacy-note">{message}</div>',
        unsafe_allow_html=True,
    )


def evidence_area(response) -> None:
    if not response.citations:
        return
    with st.expander("Evidence", expanded=False):
        for citation in response.citations:
            page = f"p. {citation.page_start}" if not citation.page_end else f"pp. {citation.page_start}-{citation.page_end}"
            st.markdown(
                f"- **{citation.policy_id}** · AISHA Handbook v{citation.handbook_version} · "
                f"{page} · Applicability: {response.applicability.value.replace('_', ' ').title()}"
            )


def ensure_conversation(service: AishaService) -> str:
    if "conversation_id" not in st.session_state:
        created = service.create_conversation("emp-alyssa", DEMO_DATE)
        st.session_state.conversation_id = created["id"]
    return st.session_state.conversation_id


def render_context(repo: Repo) -> None:
    profile = repo.get_hire_profile("emp-alyssa")
    st.markdown("### Current context")
    st.markdown(
        "<div class='context-card'><strong>Alyssa Reyes</strong><br>"
        "Management Trainee / Branch Banking Associate<br>"
        f"Branch Banking · {profile.employment_classification.title()} · {profile.work_site.replace('_',' ').title()}</div>",
        unsafe_allow_html=True,
    )
    st.markdown("<div class='context-card'><strong>Active Handbook</strong><br>AISHA Handbook v1.0</div>", unsafe_allow_html=True)
    st.caption("Confirmed Hire Profile attributes decide applicability. Chat claims never overwrite them.")


def ask_aisha(service: AishaService) -> None:
    st.markdown("## Ask AISHA")
    st.caption("Payroll · Resource Access · HR Policies")
    conversation_id = ensure_conversation(service)
    messages = service.list_messages(conversation_id)
    for message in messages:
        role = "user" if message["role"] == "hire" else "assistant"
        with st.chat_message(role):
            st.markdown(message["text"])
    prompt = st.chat_input("Ask a Payroll, Resource Access, or HR Policies question")
    if prompt:
        with st.status("Checking the active handbook…", expanded=False):
            response = service.send_message(conversation_id, prompt)
        announce(f"AISHA returned {response.type.replace('_', ' ')}.")
        with st.chat_message("assistant"):
            st.markdown(response.text)
            evidence_area(response)
        if response.type == "escalation_offer":
            st.info(f"Route: {response.route_owner} · Summary: {response.proposed_summary}")
            if st.button("Consent and create case", key=f"consent-{response.offer_id}"):
                service.consent_escalation(response.offer_id, expected_version=response.version)
                announce("Your consented escalation case was created.")


def certificate_check(service: AishaService) -> None:
    st.markdown("## Certificate Check")
    st.markdown(
        "**HRP-004 · AISHA Handbook v1.0 · pp. 78-85.** Local completeness "
        "check only—not authenticity, approval, or medical assessment."
    )
    st.caption("Accepted: one PDF, JPG, or PNG; up to 10 MB; PDF up to 3 pages.")
    acknowledged = st.checkbox(
        "I understand the certificate and extracted text are discarded; AISHA stores only the result."
    )
    upload = st.file_uploader("Certificate file", type=["pdf", "png", "jpg", "jpeg"])
    if st.button("Run local completeness check", disabled=upload is None or not acknowledged):
        with st.status("Extracting locally, validating, and cleaning up…", expanded=False):
            outcome = service.medical.check(
                upload.getvalue(), filename=upload.name, evaluation_date=DEMO_DATE,
                applicability=ApplicabilityStatus.APPLIES, acknowledged=acknowledged,
            )
        announce(f"Certificate Check outcome: {outcome.kind.replace('_', ' ')}.")
        if outcome.kind == "validation_result":
            st.success((outcome.status or "complete").replace("_", " ").title())
            codes = outcome.missing_codes + outcome.inconsistency_codes + outcome.review_codes
            if codes:
                st.write([code.replace("_", " ").title() for code in codes])
        elif outcome.kind == "retry_required":
            st.warning("Please provide one clearer image or the original digital PDF.")
        else:
            st.warning((outcome.code or outcome.kind).replace("_", " ").title())
        st.info("Submit the original certificate through the separate Official HR Document Route.")


def history(repo: Repo) -> None:
    st.markdown("## History")
    st.caption("Validation Results only. Original files and extracted content are never retained.")
    with repo.connection() as conn:
        rows = conn.execute(
            "SELECT validation_id,status,simulated_evaluation_date,handbook_version,share_state,resource_version "
            "FROM validation_results WHERE hire_id='emp-alyssa' ORDER BY created_at_utc DESC, validation_id DESC"
        ).fetchall()
    if not rows:
        st.info("No retained Validation Results yet. Private certificate files never appear here.")
        return
    for row in rows:
        with st.container(border=True):
            st.markdown(f"**{row['status'].replace('_',' ').title()}** · HRP-004 · Handbook v{row['handbook_version']}")
            st.caption(f"Evaluation date {row['simulated_evaluation_date']} · {row['share_state'].title()}")


def new_hire_view(service: AishaService, repo: Repo) -> None:
    st.markdown("**Ask AISHA · Certificate Check · History**")
    destination = st.radio(
        "New Hire destination",
        ["Ask AISHA", "Certificate Check", "History"],
        horizontal=True,
        label_visibility="collapsed",
    )
    left, right = st.columns([3, 1], gap="large")
    with left:
        if destination == "Ask AISHA":
            ask_aisha(service)
        elif destination == "Certificate Check":
            certificate_check(service)
        else:
            history(repo)
    with right:
        render_context(repo)


def hr_view(repo: Repo) -> None:
    st.markdown("## HR User")
    announce("HR sees only consented or explicitly shared structured records—never private chat or certificate content.")
    st.markdown("### Consented Escalation Cases")
    cases = repo.list_escalation_cases()
    st.info("No consented cases." if not cases else f"{len(cases)} consented case(s).")
    for case in cases:
        st.markdown(f"- **{case['status'].title()}** · {case['topic']} · {case['approved_summary']}")
    st.markdown("### Shared Validation Results")
    shared = repo.list_shared_validation_results()
    st.info("No results have been shared by Alyssa." if not shared else f"{len(shared)} shared result(s).")
    st.markdown("### Pending Attribute Change Requests")
    with repo.connection() as conn:
        requests = conn.execute("SELECT request_id,attribute_name,current_value,proposed_value FROM attribute_change_requests WHERE status='pending' ORDER BY created_at_utc").fetchall()
    st.info("No pending requests." if not requests else f"{len(requests)} pending request(s).")


def demo_controls(repo: Repo) -> None:
    with st.sidebar.expander("Demo controls", expanded=False):
        st.caption("Full Demo Reset clears product state and rotates the local certificate key. MLflow and VM backups are separate.")
        confirmed = st.checkbox("I understand this clears demo product state", key="reset-confirm")
        if st.button("Full Demo Reset", disabled=not confirmed):
            repo.full_demo_reset()
            st.session_state.clear()
            announce("Full Demo Reset completed.")


def main() -> None:
    st.set_page_config(page_title="AISHA", page_icon="💬", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown("<div class='aisha-hero'><h1>AISHA</h1><p>AI Support for Hires and Associates</p></div>", unsafe_allow_html=True)
    st.markdown(f"<small>{DISCLAIMER}</small>", unsafe_allow_html=True)
    repo, service = get_repo(), get_service()
    role = st.segmented_control("View", ["New Hire", "HR User"], default="New Hire")
    if role == "HR User":
        hr_view(repo)
    else:
        new_hire_view(service, repo)
    demo_controls(repo)


if __name__ == "__main__":
    main()
