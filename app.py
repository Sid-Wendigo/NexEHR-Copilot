
import os
import tempfile
from datetime import date, datetime
from dotenv import load_dotenv

import streamlit as st

import db
import rag
import ai_service
import pdf_gen


# =========================================================
# CONFIGURATION
# =========================================================

load_dotenv()

APP_NAME = "NexEHR Copilot"
DOCTOR_DEFAULT = "Dr. Chopper"

os.makedirs("data/uploads", exist_ok=True)
os.makedirs("generated_reports", exist_ok=True)

st.set_page_config(
    page_title=APP_NAME,
    page_icon="⚕️",
    layout="wide",
    initial_sidebar_state="expanded"
)

db.init_db()


# =========================================================
# SESSION STATE
# =========================================================

DEFAULT_STATE = {
    "active_patient_id": None,
    "active_transcript": None,
    "active_soap": None,
    "active_pdf": None,
    "consultation_id": None,
    "encounter_saved": False,
    "selected_model": None,
    "show_history": False
}

for key, value in DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = value


def reset_encounter():
    """Clear the active consultation without affecting saved records."""

    keys_to_clear = [
        "active_transcript",
        "active_soap",
        "active_pdf",
        "consultation_id",
        "encounter_saved"
    ]

    for key in keys_to_clear:
        st.session_state[key] = None if key != "encounter_saved" else False

    for key in list(st.session_state.keys()):
        if key.startswith(("transcript_editor_", "soap_editor_")):
            del st.session_state[key]


# =========================================================
# STYLING
# =========================================================

st.markdown("""
<style>
    .block-container {
        padding-top: 1.8rem;
        padding-bottom: 3rem;
        max-width: 1500px;
    }

    .brand-title {
        color: #075985;
        font-size: 1.65rem;
        font-weight: 800;
        letter-spacing: -0.5px;
    }

    .brand-subtitle {
        color: #64748B;
        font-size: 0.85rem;
    }

    .metric-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 14px;
        padding: 20px;
        min-height: 115px;
    }

    .metric-label {
        color: #64748B;
        font-size: 0.85rem;
        font-weight: 500;
    }

    .metric-value {
        color: #0F172A;
        font-size: 1.9rem;
        font-weight: 750;
        margin-top: 5px;
    }

    .section-label {
        color: #075985;
        font-weight: 700;
        font-size: 1.05rem;
        margin-bottom: 8px;
    }

    .patient-banner {
        background: #F0F9FF;
        border: 1px solid #BAE6FD;
        border-radius: 12px;
        padding: 18px;
    }

    .status-draft {
        color: #92400E;
        background: #FEF3C7;
        padding: 5px 10px;
        border-radius: 20px;
        font-weight: 600;
    }

    .status-approved {
        color: #166534;
        background: #DCFCE7;
        padding: 5px 10px;
        border-radius: 20px;
        font-weight: 600;
    }

    div[data-testid="stMetric"] {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        padding: 15px;
        border-radius: 12px;
    }

    .stButton button {
        border-radius: 9px;
        font-weight: 600;
    }

    .stButton button[kind="primary"] {
        background: #075985;
        border-color: #075985;
    }

    div[data-testid="stForm"] {
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 18px;
    }

    div[data-testid="stExpander"] {
        border: 1px solid #E2E8F0;
        border-radius: 10px;
    }

    .footer-note {
        color: #64748B;
        font-size: 0.78rem;
        text-align: center;
        padding-top: 20px;
    }
</style>
""", unsafe_allow_html=True)


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def show_metric(label, value, icon):
    st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">{icon} {label}</div>
            <div class="metric-value">{value}</div>
        </div>
    """, unsafe_allow_html=True)


def get_patient_label(patient):
    return (
        f"{patient.get('name', 'Unknown')} "
        f"(MRN-{int(patient['id']):05d})"
    )


def safe_text(value, fallback="Not documented"):
    if value is None or value == "":
        return fallback
    return str(value)


def display_list(items):
    if not items:
        st.caption("No information recorded.")
        return

    if isinstance(items, str):
        st.write(items)
        return

    for item in items:
        if isinstance(item, dict):
            description = " | ".join(
                f"{key.replace('_', ' ').title()}: {value}"
                for key, value in item.items()
                if value not in (None, "", [])
            )
            st.markdown(f"- {description}")
        else:
            st.markdown(f"- {item}")


def save_uploaded_audio(uploaded_file):
    """Save an uploaded audio file temporarily for Gemini processing."""

    filename = getattr(uploaded_file, "name", "consultation.wav")
    suffix = os.path.splitext(filename)[1].lower()

    allowed_formats = [".wav", ".mp3", ".m4a", ".ogg", ".flac"]

    if suffix not in allowed_formats:
        raise ValueError("Unsupported audio format.")

    if uploaded_file.size == 0:
        raise ValueError("The uploaded audio file is empty.")

    if uploaded_file.size > 50 * 1024 * 1024:
        raise ValueError("Audio file exceeds the 50 MB limit.")

    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=suffix
    ) as temp_file:
        temp_file.write(uploaded_file.getbuffer())
        return temp_file.name


def save_uploaded_pdf(uploaded_file):
    """Save an uploaded PDF temporarily for indexing."""

    if uploaded_file.size == 0:
        raise ValueError("The PDF file is empty.")

    if uploaded_file.size > 30 * 1024 * 1024:
        raise ValueError("PDF exceeds the 30 MB limit.")

    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".pdf"
    ) as temp_file:
        temp_file.write(uploaded_file.getbuffer())
        return temp_file.name


def get_soap_value(soap, key):
    value = soap.get(key, "")
    if value is None:
        return ""
    return value


def get_consultation_date(consultation):
    return (
        consultation.get("consultation_date")
        or consultation.get("date")
        or consultation.get("created_at")
        or "Date unavailable"
    )


def build_final_documentation(soap, patient_id):
    """Collect edited SOAP fields while preserving other AI-generated sections."""

    final_documentation = dict(soap)

    sections = [
        "subjective",
        "objective",
        "assessment",
        "plan"
    ]

    for section in sections:
        key = f"soap_editor_{patient_id}_{section}"

        if key in st.session_state:
            final_documentation[section] = st.session_state[key]

    return final_documentation


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.markdown(
        "<div class='brand-title'>⚕️ NexEHR Copilot</div>",
        unsafe_allow_html=True
    )

    st.markdown(
        "<div class='brand-subtitle'>AI-powered clinical documentation</div>",
        unsafe_allow_html=True
    )

    st.divider()

    page = st.radio(
        "WORKSPACE",
        [
            "Command Center",
            "Patient Database",
            "AI Encounter"
        ],
        label_visibility="collapsed"
    )

    st.divider()

    doctor_name = st.text_input(
        "Attending Physician",
        value=os.getenv("DOCTOR_NAME", DOCTOR_DEFAULT)
    ).strip()

    if not doctor_name:
        doctor_name = DOCTOR_DEFAULT

    st.caption("Physician name used in clinical reports.")

    st.divider()

    st.markdown("**AI Engine**")

    try:
        available_models = ai_service.get_available_models()

        if not available_models:
            available_models = [ai_service.DEFAULT_MODEL]

        default_model = ai_service.DEFAULT_MODEL

        if default_model in available_models:
            default_index = available_models.index(default_model)
        else:
            default_index = 0

        selected_model = st.selectbox(
            "Gemini Model",
            available_models,
            index=default_index
        )

    except Exception:
        selected_model = getattr(
            ai_service,
            "DEFAULT_MODEL",
            "gemini-3.5-flash-lite"
        )

        st.caption("Using configured Gemini model.")

    st.divider()

    st.caption("Powered by Google Gemini")


# =========================================================
# LOAD PATIENTS
# =========================================================

patients = db.get_patients()


# =========================================================
# 1. COMMAND CENTER
# =========================================================

if page == "Command Center":

    st.title("Command Center")

    st.caption(
        "Your clinical workspace for patient management "
        "and AI-assisted documentation."
    )

    stats = db.get_dashboard_stats()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        show_metric(
            "Total Patients",
            stats.get("patients", 0),
            "👥"
        )

    with col2:
        show_metric(
            "Total Consultations",
            stats.get("consultations", 0),
            "📋"
        )

    with col3:
        show_metric(
            "Today's Consultations",
            stats.get("today", 0),
            "🩺"
        )

    with col4:
        show_metric(
            "Pending Reviews",
            stats.get("pending", 0),
            "⏳"
        )

    st.divider()

    left, right = st.columns([1.7, 1])

    with left:

        st.subheader("Recent Consultations")

        recent = stats.get("recent", [])

        if recent:

            for consultation in recent:

                with st.container(border=True):

                    c1, c2 = st.columns([3, 1])

                    c1.markdown(
                        f"**{consultation.get('name', 'Unknown patient')}**"
                    )

                    c1.caption(
                        str(
                            consultation.get("date", "Date unavailable")
                        ).replace("T", " ")[:19]
                    )

                    status = consultation.get("status", "Saved")

                    if status == "Approved":
                        c2.success(status)
                    else:
                        c2.warning(status)

        else:
            st.info("No consultations have been recorded yet.")

    with right:

        st.subheader("Quick Actions")

        st.write(
            "Start a new patient encounter or register a patient."
        )

        if st.button(
            "➕ Register a Patient",
            use_container_width=True
        ):
            st.session_state["open_registration"] = True
            st.rerun()

        if st.button(
            "🎙️ Start AI Encounter",
            type="primary",
            use_container_width=True
        ):
            st.session_state["open_encounter"] = True
            st.rerun()

        st.caption(
            "AI-generated documentation requires physician review "
            "before approval."
        )

    st.divider()

    st.subheader("Recently Registered Patients")

    if patients:

        for patient in patients[:5]:

            with st.container(border=True):

                c1, c2 = st.columns([3, 1])

                c1.markdown(f"**{patient.get('name', 'Unknown')}**")

                c1.caption(
                    f"MRN-{int(patient['id']):05d} | "
                    f"{safe_text(patient.get('gender'))} | "
                    f"DOB: {safe_text(patient.get('dob'))}"
                )

                c2.caption(
                    f"ID: {patient['id']}"
                )

    else:
        st.info("No patients registered yet.")


# =========================================================
# 2. PATIENT DATABASE
# =========================================================

elif page == "Patient Database":

    st.title("Patient Database")

    st.caption(
        "Register patients, manage medical records, "
        "and review previous consultations."
    )

    tab_records, tab_register = st.tabs([
        "📋 Patient Records",
        "➕ Register Patient"
    ])

    # -----------------------------------------------------
    # PATIENT RECORDS
    # -----------------------------------------------------

    with tab_records:

        search = st.text_input(
            "Search patients",
            placeholder="Search by patient name or MRN..."
        )

        filtered_patients = [
            patient for patient in patients
            if (
                search.lower() in str(patient.get("name", "")).lower()
                or search.lower() in str(patient.get("id", ""))
            )
        ]

        if not filtered_patients:
            st.info("No matching patients found.")

        for patient in filtered_patients:

            patient_id = patient["id"]

            with st.expander(
                f"👤 {patient.get('name', 'Unknown')} "
                f"— MRN-{int(patient_id):05d}"
            ):

                left, right = st.columns(2)

                with left:

                    st.markdown("**Patient Information**")

                    st.write(
                        f"Date of Birth: {safe_text(patient.get('dob'))}"
                    )

                    st.write(
                        f"Gender: {safe_text(patient.get('gender'))}"
                    )

                    st.write(
                        f"Medical History: "
                        f"{safe_text(patient.get('history'))}"
                    )

                with right:

                    st.markdown("**Clinical Information**")

                    st.write(
                        f"Allergies: "
                        f"{safe_text(patient.get('allergies'))}"
                    )

                    st.write(
                        f"Current Medications: "
                        f"{safe_text(patient.get('medications'))}"
                    )

                st.divider()

                # -----------------------------------------
                # UPLOAD MEDICAL DOCUMENTS
                # -----------------------------------------

                st.markdown("**Previous Medical Records**")

                uploaded_pdf = st.file_uploader(
                    "Upload a medical PDF",
                    type=["pdf"],
                    key=f"patient_pdf_{patient_id}"
                )

                if uploaded_pdf:

                    if st.button(
                        "Process and Index PDF",
                        key=f"index_pdf_{patient_id}",
                        use_container_width=True
                    ):

                        temp_path = None

                        try:

                            with st.spinner(
                                "Extracting and indexing medical document..."
                            ):

                                temp_path = save_uploaded_pdf(uploaded_pdf)

                                chunk_count = rag.process_and_store_pdf(
                                    temp_path,
                                    patient_id
                                )

                            st.success(
                                f"Successfully indexed {chunk_count} "
                                f"document chunks."
                            )

                        except Exception as exc:
                            st.error(f"PDF processing failed: {exc}")

                        finally:

                            if temp_path and os.path.exists(temp_path):
                                os.remove(temp_path)

                try:

                    document_count = rag.get_patient_document_count(
                        patient_id
                    )

                    st.caption(
                        f"Indexed medical document chunks: {document_count}"
                    )

                except Exception:
                    st.caption("Document index information unavailable.")

                st.divider()

                # -----------------------------------------
                # CONSULTATION HISTORY
                # -----------------------------------------

                st.markdown("**Consultation History**")

                try:
                    consultations = db.get_patient_consultations(
                        patient_id
                    )
                except Exception:
                    consultations = []

                if consultations:

                    for consultation in consultations:

                        consultation_date = get_consultation_date(
                            consultation
                        )

                        with st.container(border=True):

                            st.markdown(
                                f"**{str(consultation_date)[:19]}**"
                            )

                            st.caption(
                                f"Status: "
                                f"{consultation.get('status', 'Saved')}"
                            )

                            st.write(
                                consultation.get("assessment")
                                or "No assessment recorded."
                            )

                            with st.expander("View consultation details"):

                                for section in [
                                    "subjective",
                                    "objective",
                                    "assessment",
                                    "plan"
                                ]:

                                    st.markdown(
                                        f"**{section.title()}**"
                                    )

                                    st.write(
                                        consultation.get(section)
                                        or "Not documented."
                                    )

                else:
                    st.caption("No consultations found.")

                st.divider()

                # -----------------------------------------
                # DELETE PATIENT
                # -----------------------------------------

                confirm_delete = st.checkbox(
                    "I understand that deleting this patient "
                    "will permanently remove their EHR records.",
                    key=f"confirm_delete_{patient_id}"
                )

                if st.button(
                    "Delete Patient Record",
                    key=f"delete_patient_{patient_id}",
                    disabled=not confirm_delete,
                    type="secondary"
                ):

                    try:

                        if st.session_state.active_patient_id == patient_id:
                            reset_encounter()
                            st.session_state.active_patient_id = None

                        # Remove indexed clinical documents first.
                        rag.delete_patient_documents(patient_id)

                        db.delete_patient(patient_id)

                        st.success("Patient record deleted.")

                        st.rerun()

                    except Exception as exc:
                        st.error(f"Unable to delete patient: {exc}")

    # -----------------------------------------------------
    # REGISTER PATIENT
    # -----------------------------------------------------

    with tab_register:

        st.subheader("Register New Patient")

        with st.form("register_patient_form"):

            col1, col2 = st.columns(2)

            name = col1.text_input("Full Name")

            dob = col2.date_input(
                "Date of Birth",
                value=date(1990, 1, 1),
                min_value=date(1900, 1, 1),
                max_value=date.today()
            )

            gender = col1.selectbox(
                "Gender",
                [
                    "Male",
                    "Female",
                    "Other",
                    "Prefer not to say"
                ]
            )

            allergies = col2.text_input(
                "Known Allergies",
                placeholder="Enter allergies or Unknown"
            )

            medications = st.text_area(
                "Current Medications",
                placeholder="Enter current medications..."
            )

            history = st.text_area(
                "Previous Medical History",
                placeholder="Enter relevant medical history..."
            )

            submitted = st.form_submit_button(
                "Create Patient Record",
                type="primary",
                use_container_width=True
            )

            if submitted:

                if not name.strip():
                    st.error("Patient name is required.")

                elif dob > date.today():
                    st.error("Date of birth cannot be in the future.")

                else:

                    try:

                        patient_id = db.add_patient(
                            name.strip(),
                            dob,
                            gender,
                            history,
                            allergies,
                            medications
                        )

                        st.success(
                            f"Patient registered successfully. "
                            f"MRN-{int(patient_id):05d}"
                        )

                        st.rerun()

                    except Exception as exc:
                        st.error(f"Patient registration failed: {exc}")


# =========================================================
# 3. AI ENCOUNTER
# =========================================================

elif page == "AI Encounter":

    st.title("AI Clinical Encounter")

    st.caption(
        "Convert doctor-patient conversations into structured "
        "clinical documentation using Gemini."
    )

    if not patients:

        st.warning(
            "No patients are registered. Register a patient "
            "before starting an encounter."
        )

    else:

        # -------------------------------------------------
        # SELECT PATIENT
        # -------------------------------------------------

        patient_options = {
            get_patient_label(patient): patient
            for patient in patients
        }

        selected_label = st.selectbox(
            "Select Patient",
            list(patient_options.keys())
        )

        patient = patient_options[selected_label]
        patient_id = patient["id"]

        # -------------------------------------------------
        # SESSION ISOLATION
        # -------------------------------------------------

        if st.session_state.active_patient_id != patient_id:

            reset_encounter()

            st.session_state.active_patient_id = patient_id

        # -------------------------------------------------
        # PATIENT OVERVIEW
        # -------------------------------------------------

        with st.container(border=True):

            st.markdown("### Patient Overview")

            c1, c2, c3 = st.columns(3)

            c1.markdown(f"**Name**  \n{patient.get('name', 'Unknown')}")

            c2.markdown(f"**Date of Birth**  \n{patient.get('dob', 'Unknown')}")

            c3.markdown(f"**Gender**  \n{patient.get('gender', 'Unknown')}")

            st.divider()

            c1, c2 = st.columns(2)

            c1.markdown(
                f"**Allergies**  \n"
                f"{safe_text(patient.get('allergies'))}"
            )

            c2.markdown(
                f"**Current Medications**  \n"
                f"{safe_text(patient.get('medications'))}"
            )

            st.markdown(
                f"**Medical History**  \n"
                f"{safe_text(patient.get('history'))}"
            )

        # -------------------------------------------------
        # NEW ENCOUNTER
        # -------------------------------------------------

        if st.button(
            "＋ Start New Encounter",
            use_container_width=False,
            disabled=(
                st.session_state.active_transcript is None
                and st.session_state.active_soap is None
            )
        ):

            reset_encounter()
            st.rerun()

        st.divider()

        # -------------------------------------------------
        # AUDIO INPUT
        # -------------------------------------------------

        st.markdown("### 1. Consultation Audio")

        audio_method = st.radio(
            "Choose audio input method",
            ["Record Audio", "Upload Audio"],
            horizontal=True
        )

        audio_file = None

        if audio_method == "Record Audio":

            audio_file = st.audio_input(
                "Record doctor-patient consultation"
            )

        else:

            audio_file = st.file_uploader(
                "Upload consultation audio",
                type=["wav", "mp3", "m4a", "ogg", "flac"],
                key=f"audio_upload_{patient_id}"
            )

        if audio_file:

            st.audio(audio_file)

            st.caption(
                f"File size: {audio_file.size / (1024 * 1024):.2f} MB"
            )

            if st.button(
                "🎙️ Transcribe Consultation with Gemini",
                type="primary",
                use_container_width=True
            ):

                temp_path = None

                try:

                    with st.spinner(
                        "Gemini is transcribing the consultation..."
                    ):

                        temp_path = save_uploaded_audio(audio_file)

                        transcript = ai_service.process_audio(temp_path)

                        if not transcript or not transcript.strip():
                            raise ValueError(
                                "Gemini returned an empty transcript."
                            )

                        st.session_state.active_transcript = transcript
                        st.session_state.active_soap = None
                        st.session_state.active_pdf = None
                        st.session_state.consultation_id = None
                        st.session_state.encounter_saved = False

                        transcript_key = f"transcript_editor_{patient_id}"

                        st.session_state[transcript_key] = transcript

                        for key in list(st.session_state.keys()):
                            if key.startswith(f"soap_editor_{patient_id}_"):
                                del st.session_state[key]

                    st.success("Transcription completed successfully.")

                except Exception as exc:
                    st.error(f"Transcription failed: {exc}")

                finally:

                    if temp_path and os.path.exists(temp_path):
                        os.remove(temp_path)

        # -------------------------------------------------
        # TRANSCRIPT REVIEW
        # -------------------------------------------------

        transcript_key = f"transcript_editor_{patient_id}"

        if st.session_state.active_transcript:

            st.divider()

            st.markdown("### 2. Review Consultation Transcript")

            st.info(
                "Review the transcript carefully. Correct names, "
                "medical terminology, medication details, dosages "
                "and unclear statements before generating the note."
            )

            if transcript_key not in st.session_state:
                st.session_state[transcript_key] = (
                    st.session_state.active_transcript
                )

            edited_transcript = st.text_area(
                "Editable consultation transcript",
                height=300,
                key=transcript_key
            )

            if st.button(
                "🧠 Generate Clinical Documentation",
                type="primary",
                use_container_width=True,
                disabled=st.session_state.encounter_saved
            ):

                if not edited_transcript.strip():

                    st.error("Transcript cannot be empty.")

                else:

                    try:

                        with st.status(
                            "Gemini is generating clinical documentation...",
                            expanded=True
                        ) as status:

                            st.write("Retrieving patient medical history...")

                            historical_context = rag.retrieve_patient_history(
                                patient_id,
                                edited_transcript,
                                k=8
                            )

                            st.write("Analyzing the consultation with Gemini...")

                            documentation = ai_service.generate_soap_note(
                                transcript=edited_transcript,
                                historical_context=historical_context,
                                model_name=selected_model,
                                patient_data=patient
                            )

                            if not isinstance(documentation, dict):
                                raise ValueError(
                                    "The AI service did not return "
                                    "structured clinical documentation."
                                )

                            st.session_state.active_soap = documentation

                            st.session_state.active_transcript = edited_transcript

                            # Initialize editable SOAP fields.
                            for section in [
                                "subjective",
                                "objective",
                                "assessment",
                                "plan"
                            ]:

                                key = f"soap_editor_{patient_id}_{section}"

                                st.session_state[key] = documentation.get(
                                    section,
                                    ""
                                ) or ""

                            st.session_state.active_pdf = None
                            st.session_state.encounter_saved = False

                            status.update(
                                label="Clinical documentation generated.",
                                state="complete",
                                expanded=False
                            )

                        st.success(
                            "Gemini generated the clinical documentation. "
                            "Please review it before approval."
                        )

                    except Exception as exc:
                        st.error(
                            f"Clinical documentation generation failed: {exc}"
                        )

        # -------------------------------------------------
        # CLINICAL DOCUMENTATION REVIEW
        # -------------------------------------------------

        if st.session_state.active_soap:

            soap = st.session_state.active_soap

            st.divider()

            st.markdown("### 3. Clinical Documentation")

            st.warning(
                "This is AI-generated draft documentation. "
                "The attending physician must verify and approve "
                "all clinical information."
            )

            tab_summary, tab_treatment, tab_soap, tab_transcript = st.tabs([
                "🧠 AI Insights",
                "💊 Treatment & Follow-up",
                "📝 SOAP Editor",
                "🎙️ Transcript"
            ])

            # =============================================
            # AI INSIGHTS
            # =============================================

            with tab_summary:

                st.markdown("#### Clinical Summary")

                st.write(
                    soap.get("clinical_summary")
                    or "No clinical summary generated."
                )

                st.divider()

                risk = str(
                    soap.get("risk_level", "Not Assessed")
                ).title()

                if risk.lower() in ["high", "critical"]:
                    st.error(f"Risk Level: {risk}")
                elif risk.lower() == "moderate":
                    st.warning(f"Risk Level: {risk}")
                else:
                    st.info(f"Risk Level: {risk}")

                st.markdown("#### AI Clinical Insights")

                st.write(
                    soap.get("ai_insights")
                    or "No additional AI insights."
                )

                if soap.get("red_flags"):

                    st.markdown("#### Red Flags Requiring Review")

                    for flag in soap["red_flags"]:
                        st.warning(str(flag))

                if soap.get("missing_information"):

                    st.markdown("#### Missing Information")

                    display_list(soap["missing_information"])

                if soap.get("differential_diagnoses"):

                    st.markdown("#### Differential Diagnoses")

                    display_list(soap["differential_diagnoses"])

                if soap.get("icd_10_codes"):

                    st.markdown("#### Suggested ICD-10 Codes")

                    display_list(soap["icd_10_codes"])

                st.caption(
                    "AI insights are decision-support suggestions, "
                    "not independently verified diagnoses."
                )

            # =============================================
            # TREATMENT PLAN
            # =============================================

            with tab_treatment:

                st.markdown("#### Treatment Plan")

                display_list(soap.get("treatment_plan"))

                st.divider()

                st.markdown("#### Medications")

                display_list(soap.get("medications"))

                st.divider()

                st.markdown("#### Investigations")

                display_list(soap.get("investigations"))

                st.divider()

                st.markdown("#### Patient Instructions")

                display_list(soap.get("patient_instructions"))

                st.divider()

                st.markdown("#### Follow-up")

                display_list(soap.get("follow_up"))

                st.caption(
                    "Review all medication and treatment suggestions. "
                    "Only physician-confirmed decisions should be entered "
                    "into the patient's ongoing medical record."
                )

            # =============================================
            # SOAP EDITOR
            # =============================================

            with tab_soap:

                st.markdown("#### Subjective")

                st.text_area(
                    "Subjective Findings",
                    key=f"soap_editor_{patient_id}_subjective",
                    height=140,
                    disabled=st.session_state.encounter_saved
                )

                st.markdown("#### Objective")

                st.text_area(
                    "Objective Findings",
                    key=f"soap_editor_{patient_id}_objective",
                    height=140,
                    disabled=st.session_state.encounter_saved
                )

                st.markdown("#### Assessment")

                st.text_area(
                    "Clinical Assessment",
                    key=f"soap_editor_{patient_id}_assessment",
                    height=140,
                    disabled=st.session_state.encounter_saved
                )

                st.markdown("#### Plan")

                st.text_area(
                    "Treatment and Follow-up Plan",
                    key=f"soap_editor_{patient_id}_plan",
                    height=140,
                    disabled=st.session_state.encounter_saved
                )

                st.divider()

                if not st.session_state.encounter_saved:

                    st.checkbox(
                        "I have reviewed the transcript and "
                        "verified the generated clinical documentation.",
                        key=f"physician_review_{patient_id}"
                    )

                    review_confirmed = st.session_state.get(
                        f"physician_review_{patient_id}",
                        False
                    )

                    if st.button(
                        "✓ Approve and Save Clinical Note",
                        type="primary",
                        use_container_width=True,
                        disabled=not review_confirmed
                    ):

                        try:

                            final_documentation = build_final_documentation(
                                soap,
                                patient_id
                            )

                            with st.spinner(
                                "Saving consultation and generating report..."
                            ):

                                # Save as a draft first.
                                consultation_id = db.save_consultation(
                                    patient_id=patient_id,
                                    transcript=st.session_state.active_transcript,
                                    soap_dict=final_documentation,
                                    doctor_name=doctor_name,
                                    status="Draft"
                                )

                                # Mark as approved after physician review.
                                db.approve_consultation(
                                    consultation_id,
                                    performed_by=doctor_name
                                )

                                # Index only the approved consultation.
                                try:

                                    rag.add_consultation_to_knowledge_base(
                                        patient_id=patient_id,
                                        consultation_id=consultation_id,
                                        documentation=final_documentation
                                    )

                                except Exception as indexing_error:

                                    st.warning(
                                        "Consultation was approved, but "
                                        "historical indexing failed: "
                                        f"{indexing_error}"
                                    )

                                # Generate the final clinical PDF.
                                pdf_path = pdf_gen.generate_clinical_pdf(
                                    patient_data=patient,
                                    final_soap=final_documentation,
                                    doctor_name=doctor_name,
                                    consultation_id=consultation_id
                                )

                                # Associate PDF with the consultation.
                                db.set_consultation_pdf(
                                    consultation_id,
                                    pdf_path,
                                    performed_by=doctor_name
                                )

                            st.session_state.active_soap = final_documentation
                            st.session_state.active_pdf = pdf_path
                            st.session_state.consultation_id = consultation_id
                            st.session_state.encounter_saved = True

                            st.success(
                                "Clinical note approved and saved successfully."
                            )

                            st.rerun()

                        except Exception as exc:

                            st.error(
                                f"Unable to complete the approval workflow: {exc}"
                            )

            # =============================================
            # TRANSCRIPT TAB
            # =============================================

            with tab_transcript:

                st.text_area(
                    "Verified Consultation Transcript",
                    value=st.session_state.active_transcript or "",
                    height=350,
                    disabled=True
                )

        # -------------------------------------------------
        # PDF EXPORT
        # -------------------------------------------------

        if st.session_state.active_pdf:

            st.divider()

            st.markdown("### 4. Clinical Report")

            st.success(
                f"Consultation #{st.session_state.consultation_id} "
                "has been approved and saved."
            )

            st.caption(
                f"Attending Physician: {doctor_name}"
            )

            pdf_path = st.session_state.active_pdf

            if os.path.exists(pdf_path):

                with open(pdf_path, "rb") as pdf_file:

                    pdf_bytes = pdf_file.read()

                st.download_button(
                    label="📥 Download Clinical Report",
                    data=pdf_bytes,
                    file_name=os.path.basename(pdf_path),
                    mime="application/pdf",
                    type="primary",
                    use_container_width=True
                )

                with st.expander("Preview report information"):

                    st.write(
                        f"Patient: {patient.get('name', 'Unknown')}"
                    )

                    st.write(
                        f"Consultation ID: "
                        f"{st.session_state.consultation_id}"
                    )

                    st.write(
                        f"Doctor: {doctor_name}"
                    )

                    st.write(
                        f"Report: {os.path.basename(pdf_path)}"
                    )

            else:

                st.error(
                    "The PDF file could not be found. "
                    "The consultation remains saved in the EHR."
                )

                if st.button("Regenerate Clinical PDF"):

                    try:

                        regenerated_path = pdf_gen.generate_clinical_pdf(
                            patient_data=patient,
                            final_soap=st.session_state.active_soap,
                            doctor_name=doctor_name,
                            consultation_id=st.session_state.consultation_id
                        )

                        db.set_consultation_pdf(
                            st.session_state.consultation_id,
                            regenerated_path,
                            performed_by=doctor_name
                        )

                        st.session_state.active_pdf = regenerated_path

                        st.success("PDF regenerated successfully.")

                        st.rerun()

                    except Exception as exc:
                        st.error(f"PDF generation failed: {exc}")


# =========================================================
# FOOTER
# =========================================================

st.markdown("---")

st.markdown(
    """
    <div class="footer-note">
        NexEHR Copilot · AI-assisted clinical documentation
        <br>
        All AI-generated clinical content must be reviewed and
        approved by a qualified healthcare professional.
    </div>
    """,
    unsafe_allow_html=True
)
