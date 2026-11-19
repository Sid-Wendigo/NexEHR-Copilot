
import os
import mimetypes
from typing import List, Optional

from dotenv import load_dotenv
from google import genai
from google.genai import types

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field


# =========================================================
# CONFIGURATION
# =========================================================

load_dotenv()

API_KEY = os.getenv("GOOGLE_API_KEY")

DEFAULT_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.5-flash-lite"
)

TRANSCRIPTION_MODEL = os.getenv(
    "TRANSCRIPTION_MODEL",
    DEFAULT_MODEL
)

if not API_KEY:
    raise RuntimeError(
        "GOOGLE_API_KEY is missing. Add it to your .env file."
    )

client = genai.Client(api_key=API_KEY)


# =========================================================
# STRUCTURED CLINICAL DATA MODELS
# =========================================================

class MedicationItem(BaseModel):
    name: str = Field(
        description="Medication name."
    )

    dosage: str = Field(
        description="Dosage, only when supported by the source."
    )

    route: str = Field(
        description="Route of administration, if documented."
    )

    frequency: str = Field(
        description="Frequency, if documented."
    )

    duration: str = Field(
        description="Duration, if documented."
    )

    status: str = Field(
        description=(
            "One of: Existing medication, Explicitly prescribed, "
            "Proposed for physician review."
        )
    )

    rationale: str = Field(
        description="Reason for the medication or Not documented."
    )


class InvestigationItem(BaseModel):
    name: str = Field(
        description="Investigation or diagnostic test."
    )

    reason: str = Field(
        description="Clinical reason for considering the test."
    )

    priority: str = Field(
        description="Routine, Recommended or Urgent, if supported."
    )

    status: str = Field(
        description=(
            "One of: Discussed, Ordered, Proposed for review."
        )
    )


class TreatmentItem(BaseModel):
    recommendation: str = Field(
        description="Specific proposed treatment or intervention."
    )

    rationale: str = Field(
        description="Clinical rationale based on available information."
    )

    category: str = Field(
        description=(
            "Medication, Investigation, Lifestyle, "
            "Supportive care or Other."
        )
    )

    priority: str = Field(
        description="Routine, Recommended or Urgent."
    )


class FollowUpItem(BaseModel):
    instruction: str = Field(
        description="Follow-up instruction."
    )

    timeframe: str = Field(
        description="Timeframe, if explicitly available or clinically justified."
    )


class ClinicalDocumentation(BaseModel):
    """
    Complete structured clinical documentation.

    This schema is used by Gemini to generate all clinical
    content consumed by the application, database and PDF.
    """

    # -----------------------------------------------------
    # ENCOUNTER SUMMARY
    # -----------------------------------------------------

    chief_complaint: str = Field(
        description="Main reason for the consultation."
    )

    clinical_summary: str = Field(
        description=(
            "Concise professional summary of the entire "
            "consultation and relevant clinical context."
        )
    )

    # -----------------------------------------------------
    # SOAP
    # -----------------------------------------------------

    subjective: str = Field(
        description=(
            "Patient-reported symptoms, history of present illness, "
            "duration, severity and relevant review of systems."
        )
    )

    objective: str = Field(
        description=(
            "Examination findings, vital signs and investigation "
            "results explicitly available. Never invent findings."
        )
    )

    assessment: str = Field(
        description=(
            "Primary clinical assessment, supporting evidence, "
            "and distinction between confirmed and suspected conditions."
        )
    )

    plan: str = Field(
        description=(
            "Concise SOAP plan documenting decisions and actions "
            "actually discussed or ordered during the consultation."
        )
    )

    # -----------------------------------------------------
    # CLINICAL HISTORY
    # -----------------------------------------------------

    relevant_history: str = Field(
        description=(
            "Relevant previous medical and surgical history "
            "from the patient record and consultation."
        )
    )

    current_medications_summary: str = Field(
        description="Summary of known current medications."
    )

    allergies_summary: str = Field(
        description="Known allergies and reactions, if documented."
    )

    # -----------------------------------------------------
    # TREATMENT PLAN
    # -----------------------------------------------------

    treatment_plan: List[TreatmentItem] = Field(
        description=(
            "Detailed proposed treatment recommendations. "
            "Clearly distinguish discussed decisions from suggestions."
        )
    )

    medications: List[MedicationItem] = Field(
        description=(
            "Existing medications, explicitly prescribed medications "
            "and proposed medication options. Never invent dosage."
        )
    )

    investigations: List[InvestigationItem] = Field(
        description=(
            "Investigations explicitly ordered or proposed "
            "for physician consideration."
        )
    )

    # -----------------------------------------------------
    # FOLLOW-UP AND PATIENT COUNSELLING
    # -----------------------------------------------------

    patient_instructions: List[str] = Field(
        description=(
            "Patient counselling, lifestyle guidance and "
            "self-care instructions supported by the encounter."
        )
    )

    follow_up: List[FollowUpItem] = Field(
        description="Follow-up recommendations and review timeframe."
    )

    # -----------------------------------------------------
    # DIAGNOSTIC INFORMATION
    # -----------------------------------------------------

    differential_diagnoses: List[str] = Field(
        description=(
            "Relevant possible alternative diagnoses. "
            "Do not present them as confirmed."
        )
    )

    icd_10_codes: List[str] = Field(
        description=(
            "Suggested ICD-10 codes supported by available evidence. "
            "Return an empty list if uncertain."
        )
    )

    # -----------------------------------------------------
    # SAFETY AND CLINICAL REVIEW
    # -----------------------------------------------------

    risk_level: str = Field(
        description=(
            "Low, Moderate, High, Critical or Not Assessed. "
            "Base this on available information."
        )
    )

    red_flags: List[str] = Field(
        description=(
            "Important warning signs, safety concerns and "
            "urgent issues requiring clinician attention."
        )
    )

    missing_information: List[str] = Field(
        description=(
            "Clinically relevant missing information that "
            "should be clarified by the physician."
        )
    )

    ai_insights: str = Field(
        description=(
            "Additional clinical considerations, potential "
            "documentation gaps and relevant observations "
            "for physician review."
        )
    )

    # -----------------------------------------------------
    # EHR UPDATE CANDIDATES
    # -----------------------------------------------------

    discovered_history: str = Field(
        description=(
            "New medical history explicitly disclosed during "
            "the consultation and not already documented. "
            "Return None if there is no new history."
        )
    )

    discovered_medications: str = Field(
        description=(
            "New long-term medications explicitly disclosed "
            "during the consultation. Do not treat proposed "
            "medications as existing medications."
        )
    )


# Backwards-compatible name for existing code.
SOAPNote = ClinicalDocumentation


# =========================================================
# MODEL DISCOVERY
# =========================================================

def get_available_models():
    try:
        models = client.models.list()

        available = []

        for model in models:
            name = model.name.replace("models/", "")

            if (
                name.startswith("gemini-")
                and "transcribe" not in name.lower()
            ):
                available.append(name)

        available = sorted(set(available), reverse=True)

        if DEFAULT_MODEL not in available:
            available.insert(0, DEFAULT_MODEL)

        return available

    except Exception as e:
        print(f"Model discovery error: {e}")
        return [DEFAULT_MODEL]


# =========================================================
# AUDIO TRANSCRIPTION
# =========================================================

def process_audio(file_path):
    """
    Transcribes a doctor-patient consultation using Gemini.

    Returns a speaker-labelled transcript.
    """

    if not os.path.exists(file_path):
        raise FileNotFoundError(
            f"Audio file not found: {file_path}"
        )

    file_size = os.path.getsize(file_path)

    if file_size == 0:
        raise ValueError("The audio file is empty.")

    if file_size > 19 * 1024 * 1024:
        raise ValueError(
            "Audio file is too large for inline transcription. "
            "Please compress it or use a shorter recording."
        )

    mime_type, _ = mimetypes.guess_type(file_path)

    if not mime_type:
        mime_type = "audio/wav"

    supported_formats = {
        "audio/wav",
        "audio/x-wav",
        "audio/mp3",
        "audio/mpeg",
        "audio/aiff",
        "audio/aac",
        "audio/ogg",
        "audio/flac",
        "audio/mp4",
        "audio/m4a",
        "audio/webm",
        "audio/opus"
    }

    if mime_type not in supported_formats:
        raise ValueError(
            f"Unsupported audio format: {mime_type}"
        )

    transcription_prompt = """
    Transcribe the attached doctor-patient consultation.

    STRICT INSTRUCTIONS:

    1. Transcribe the complete conversation accurately.
    2. Identify speakers as DOCTOR and PATIENT when possible.
    3. Put each speaker's dialogue on a separate line.
    4. Preserve medical terminology, medication names,
       dosages, frequencies and measurements.
    5. Preserve the original meaning.
    6. Do not summarize or generate clinical notes.
    7. Do not invent words when audio is unclear.
    8. Mark unintelligible portions as [unclear].
    9. Preserve the original spoken language.
    10. Do not translate the conversation.

    OUTPUT:

    DOCTOR: Spoken dialogue
    PATIENT: Spoken dialogue

    Return only the transcript.
    """

    try:
        with open(file_path, "rb") as audio:
            audio_bytes = audio.read()

        print(
            f"Transcribing with model: {TRANSCRIPTION_MODEL}"
        )

        response = client.models.generate_content(
            model=TRANSCRIPTION_MODEL,
            contents=[
                types.Part.from_bytes(
                    data=audio_bytes,
                    mime_type=mime_type
                ),
                transcription_prompt
            ]
        )

        transcript = response.text

        if not transcript or not transcript.strip():
            raise ValueError(
                "Gemini returned an empty transcription."
            )

        print("Transcription completed successfully.")

        return transcript.strip()

    except Exception as e:
        print(f"Audio transcription error: {e}")

        raise RuntimeError(
            f"Audio transcription failed: {str(e)}"
        ) from e


# =========================================================
# CLINICAL DOCUMENTATION GENERATION
# =========================================================

def generate_clinical_documentation(
    transcript,
    historical_context="",
    model_name=None,
    patient_data=None
):
    """
    Generates complete structured clinical documentation
    using Gemini.

    Returns a dictionary compatible with:
        - Streamlit clinical review
        - SQLite EHR storage
        - PDF report generation
    """

    if not transcript or not transcript.strip():
        raise ValueError(
            "Cannot generate documentation from an empty transcript."
        )

    selected_model = model_name or DEFAULT_MODEL

    historical_context = (
        historical_context.strip()
        if historical_context
        else "No previous patient records were found."
    )

    if patient_data:
        patient_details = f"""
        Patient ID: {patient_data.get('id', 'Not provided')}
        Patient Name: {patient_data.get('name', 'Not provided')}
        Date of Birth: {patient_data.get('dob', 'Not provided')}
        Gender: {patient_data.get('gender', 'Not provided')}
        Known Allergies: {patient_data.get('allergies', 'Not documented')}
        Existing Medical History: {patient_data.get('history', 'Not documented')}
        Existing Medications: {patient_data.get('medications', 'Not documented')}
        """
    else:
        patient_details = "Patient details not provided."

    prompt = f"""
You are NexEHR Copilot, an AI clinical documentation
assistant supporting a qualified medical professional.

Your task is to analyze the supplied doctor-patient
conversation and available patient records.

Generate a complete, professional and structured
clinical documentation draft.

==================================================
PATIENT INFORMATION
==================================================

{patient_details}

==================================================
PREVIOUS PATIENT RECORDS
==================================================

{historical_context}

==================================================
CURRENT CONSULTATION TRANSCRIPT
==================================================

{transcript}

==================================================
CORE CLINICAL DOCUMENTATION RULES
==================================================

1. SOURCE ACCURACY

Use the consultation transcript and historical records
as the sources of patient-specific facts.

Do not fabricate:
- Symptoms
- Examination findings
- Vital signs
- Diagnoses
- Laboratory results
- Medication prescriptions
- Medication dosages
- Allergies
- Medical history
- Follow-up appointments

If information is unavailable, clearly state
"Not documented" or return an empty list.

2. DISTINGUISH HISTORICAL AND CURRENT INFORMATION

Clearly distinguish:
- Previous medical history
- Current symptoms
- Current medications
- Newly disclosed history
- New treatment decisions

Do not interpret a proposed medication as a medication
the patient is already taking.

3. SOAP DOCUMENTATION

SUBJECTIVE:
Document the chief complaint, symptoms, duration,
severity, progression and relevant patient-reported history.

OBJECTIVE:
Include only documented examination findings,
measurements, vital signs and investigation results.

ASSESSMENT:
Document the primary clinical impression and
supporting evidence.

Clearly distinguish confirmed diagnoses from
suspected diagnoses.

PLAN:
Record the actual decisions and actions discussed
or ordered during the consultation.

4. CLINICAL SUMMARY

Create a concise but meaningful clinical summary
that captures the important details of the encounter.

5. TREATMENT PLAN

Generate a structured treatment plan for physician review.

Include relevant recommendations for:
- Treatment options
- Medication considerations
- Investigations
- Supportive care
- Lifestyle recommendations
- Patient counselling
- Follow-up

IMPORTANT:

Do not issue autonomous prescriptions.

If a medication is explicitly prescribed in the
consultation, record it as "Explicitly prescribed".

If it is only an AI-generated consideration,
record it as "Proposed for physician review".

Never invent a dosage, route, frequency or duration.

6. INVESTIGATIONS

Separate investigations that were actually ordered
from investigations that are only suggested.

Never claim that a test was ordered if it was merely
recommended for consideration.

7. DIFFERENTIAL DIAGNOSES

Suggest relevant alternatives only when supported
by the available clinical information.

Do not present a differential diagnosis as confirmed.

8. ICD-10

Provide suggested ICD-10 codes only when there is
sufficient supporting information.

Otherwise return an empty list.

9. RISK AND RED FLAGS

Identify important warning signs and safety concerns.

Do not assign a high-risk category without evidence.

Use "Not Assessed" if the available information
is insufficient for a meaningful risk assessment.

10. MISSING INFORMATION

Identify clinically relevant information that should
be clarified, such as missing vitals, symptom duration,
allergy details or examination findings.

11. PATIENT INSTRUCTIONS

Generate clear patient-facing instructions only when
they are appropriate and supported by the clinical context.

12. EHR UPDATE CANDIDATES

Identify new medical history and long-term medications
explicitly disclosed in the consultation.

Do not include AI-proposed treatments in these fields.

Do not repeat information already present in the
historical patient records.

==================================================
WRITING STYLE
==================================================

- Use professional medical terminology.
- Be concise but clinically complete.
- Use clear, structured language.
- Avoid unnecessary repetition.
- Preserve clinically important details.
- Mark uncertainty explicitly.
- Do not infer missing information as fact.
- Do not replace physician judgement.

The generated document is a draft for physician
review and approval.

Return every field in the required structured schema.
"""

    try:
        print(
            f"Generating clinical documentation using: {selected_model}"
        )

        llm = ChatGoogleGenerativeAI(
            model=selected_model,
            temperature=0,
            google_api_key=API_KEY
        )

        structured_llm = llm.with_structured_output(
            ClinicalDocumentation,
            method="json_schema"
        )

        result = structured_llm.invoke(prompt)

        if isinstance(result, BaseModel):
            documentation = result.model_dump()

        elif isinstance(result, dict):
            documentation = result

        else:
            raise ValueError(
                "Unexpected Gemini response format."
            )

        # Basic output validation.
        required_fields = [
            "chief_complaint",
            "clinical_summary",
            "subjective",
            "objective",
            "assessment",
            "plan",
            "treatment_plan",
            "medications",
            "investigations",
            "follow_up",
            "risk_level"
        ]

        missing_fields = [
            field for field in required_fields
            if field not in documentation
        ]

        if missing_fields:
            raise ValueError(
                "Gemini response is missing required fields: "
                + ", ".join(missing_fields)
            )

        # Ensure collection fields always have list values.
        list_fields = [
            "treatment_plan",
            "medications",
            "investigations",
            "patient_instructions",
            "follow_up",
            "differential_diagnoses",
            "icd_10_codes",
            "red_flags",
            "missing_information"
        ]

        for field in list_fields:
            if not isinstance(documentation.get(field), list):
                documentation[field] = []

        print("Clinical documentation generated successfully.")

        return documentation

    except Exception as e:
        print(f"Clinical documentation error: {e}")

        raise RuntimeError(
            f"Clinical documentation generation failed: {str(e)}"
        ) from e


# =========================================================
# BACKWARDS-COMPATIBLE FUNCTION
# =========================================================

def generate_soap_note(
    transcript,
    historical_context,
    model_name=None,
    patient_data=None
):
    """
    Maintains compatibility with the existing app.py.

    Although the function retains its original name,
    it now generates the complete clinical documentation.
    """

    return generate_clinical_documentation(
        transcript=transcript,
        historical_context=historical_context,
        model_name=model_name,
        patient_data=patient_data
    )
