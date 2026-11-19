
import sqlite3
import json
import os

from datetime import datetime
from contextlib import contextmanager


# =========================================================
# CONFIGURATION
# =========================================================

DB_NAME = os.getenv("EHR_DB_NAME", "ehr_system.db")

DEFAULT_DOCTOR_NAME = "Dr. Chopper"


# =========================================================
# DATABASE CONNECTION
# =========================================================

@contextmanager
def get_connection():

    conn = sqlite3.connect(
        DB_NAME,
        timeout=30
    )

    conn.row_factory = sqlite3.Row

    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 30000")

    try:
        yield conn
        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


# =========================================================
# JSON HELPERS
# =========================================================

def serialize_json(value):

    if value is None:
        value = []

    return json.dumps(
        value,
        ensure_ascii=False
    )


def deserialize_json(value, default=None):

    if default is None:
        default = []

    if not value:
        return default

    try:
        return json.loads(value)

    except (json.JSONDecodeError, TypeError):
        return default


def get_json_fields():

    return [
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


# =========================================================
# DATABASE INITIALIZATION
# =========================================================

def init_db():

    with get_connection() as conn:

        # -------------------------------------------------
        # PATIENTS
        # -------------------------------------------------

        conn.execute("""
            CREATE TABLE IF NOT EXISTS patients (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                name TEXT NOT NULL,

                dob TEXT,

                gender TEXT,

                history TEXT DEFAULT '',

                allergies TEXT DEFAULT '',

                medications TEXT DEFAULT '',

                created_at TEXT,

                updated_at TEXT
            )
        """)

        # -------------------------------------------------
        # CONSULTATIONS
        # -------------------------------------------------

        conn.execute("""
            CREATE TABLE IF NOT EXISTS consultations (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                patient_id INTEGER NOT NULL,

                date TEXT,

                transcript TEXT,

                subjective TEXT,

                objective TEXT,

                assessment TEXT,

                plan TEXT,

                status TEXT DEFAULT 'Draft',

                doctor_name TEXT DEFAULT 'Dr. Chopper',

                consultation_type TEXT DEFAULT 'General',

                FOREIGN KEY(patient_id)
                    REFERENCES patients(id)
                    ON DELETE CASCADE
            )
        """)

        # -------------------------------------------------
        # CONSULTATION MIGRATIONS
        # -------------------------------------------------

        existing_columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(consultations)"
            ).fetchall()
        }

        migrations = {

            "status": "TEXT DEFAULT 'Draft'",

            "doctor_name": "TEXT DEFAULT 'Dr. Chopper'",

            "consultation_type": "TEXT DEFAULT 'General'",

            "chief_complaint": "TEXT DEFAULT ''",

            "clinical_summary": "TEXT DEFAULT ''",

            "relevant_history": "TEXT DEFAULT ''",

            "current_medications_summary": "TEXT DEFAULT ''",

            "allergies_summary": "TEXT DEFAULT ''",

            "treatment_plan": "TEXT DEFAULT '[]'",

            "medications": "TEXT DEFAULT '[]'",

            "investigations": "TEXT DEFAULT '[]'",

            "patient_instructions": "TEXT DEFAULT '[]'",

            "follow_up": "TEXT DEFAULT '[]'",

            "differential_diagnoses": "TEXT DEFAULT '[]'",

            "icd_10_codes": "TEXT DEFAULT '[]'",

            "red_flags": "TEXT DEFAULT '[]'",

            "missing_information": "TEXT DEFAULT '[]'",

            "risk_level": "TEXT DEFAULT 'Not Assessed'",

            "ai_insights": "TEXT DEFAULT ''",

            "discovered_history": "TEXT DEFAULT ''",

            "discovered_medications": "TEXT DEFAULT ''",

            "pdf_path": "TEXT DEFAULT ''",

            "approved_at": "TEXT",

            "updated_at": "TEXT"
        }

        for column, definition in migrations.items():

            if column not in existing_columns:

                conn.execute(
                    f"""
                    ALTER TABLE consultations
                    ADD COLUMN {column} {definition}
                    """
                )

        # -------------------------------------------------
        # AUDIT LOG
        # -------------------------------------------------

        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                patient_id INTEGER,

                consultation_id INTEGER,

                action TEXT NOT NULL,

                performed_by TEXT,

                details TEXT DEFAULT '',

                created_at TEXT,

                FOREIGN KEY(patient_id)
                    REFERENCES patients(id)
                    ON DELETE SET NULL,

                FOREIGN KEY(consultation_id)
                    REFERENCES consultations(id)
                    ON DELETE SET NULL
            )
        """)

        # -------------------------------------------------
        # INDEXES
        # -------------------------------------------------

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_patient_consultations
            ON consultations(patient_id, date)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_consultation_status
            ON consultations(status)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_patient
            ON audit_logs(patient_id, created_at)
        """)

        # -------------------------------------------------
        # PATIENT MIGRATIONS
        # -------------------------------------------------

        patient_columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(patients)"
            ).fetchall()
        }

        if "updated_at" not in patient_columns:

            conn.execute("""
                ALTER TABLE patients
                ADD COLUMN updated_at TEXT
            """)


# =========================================================
# AUDIT LOGGING
# =========================================================

def _write_audit_log(
    conn,
    action,
    patient_id=None,
    consultation_id=None,
    performed_by=DEFAULT_DOCTOR_NAME,
    details=""
):

    conn.execute("""
        INSERT INTO audit_logs (

            patient_id,
            consultation_id,
            action,
            performed_by,
            details,
            created_at

        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        patient_id,
        consultation_id,
        action,
        performed_by,
        details,
        datetime.now().isoformat()
    ))


def get_audit_logs(patient_id=None, limit=100):

    with get_connection() as conn:

        if patient_id is not None:

            rows = conn.execute("""
                SELECT *
                FROM audit_logs
                WHERE patient_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (
                patient_id,
                limit
            )).fetchall()

        else:

            rows = conn.execute("""
                SELECT *
                FROM audit_logs
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,)).fetchall()

        return [dict(row) for row in rows]


# =========================================================
# PATIENT MANAGEMENT
# =========================================================

def add_patient(
    name,
    dob,
    gender,
    history="",
    allergies="",
    medications=""
):

    if not name or not name.strip():

        raise ValueError(
            "Patient name is required."
        )

    now = datetime.now().isoformat()

    with get_connection() as conn:

        cursor = conn.execute("""
            INSERT INTO patients (

                name,
                dob,
                gender,
                history,
                allergies,
                medications,
                created_at,
                updated_at

            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            name.strip(),
            str(dob),
            gender,
            history or "",
            allergies or "",
            medications or "",
            now,
            now
        ))

        patient_id = cursor.lastrowid

        _write_audit_log(
            conn,
            action="PATIENT_REGISTERED",
            patient_id=patient_id,
            details="New patient record created."
        )

        return patient_id


def get_patients():

    with get_connection() as conn:

        rows = conn.execute("""
            SELECT *
            FROM patients
            ORDER BY name COLLATE NOCASE
        """).fetchall()

        return [dict(row) for row in rows]


def get_patient(patient_id):

    with get_connection() as conn:

        row = conn.execute("""
            SELECT *
            FROM patients
            WHERE id = ?
        """, (patient_id,)).fetchone()

        return dict(row) if row else None


def search_patients(search_term):

    term = f"%{search_term.strip()}%"

    with get_connection() as conn:

        rows = conn.execute("""
            SELECT *
            FROM patients
            WHERE name LIKE ?
               OR CAST(id AS TEXT) LIKE ?
            ORDER BY name COLLATE NOCASE
        """, (
            term,
            term
        )).fetchall()

        return [dict(row) for row in rows]


def update_patient(
    patient_id,
    name=None,
    dob=None,
    gender=None,
    history=None,
    allergies=None,
    medications=None,
    performed_by=DEFAULT_DOCTOR_NAME
):

    with get_connection() as conn:

        existing = conn.execute("""
            SELECT *
            FROM patients
            WHERE id = ?
        """, (patient_id,)).fetchone()

        if not existing:

            raise ValueError(
                "Patient not found."
            )

        values = {
            "name": name if name is not None else existing["name"],
            "dob": str(dob) if dob is not None else existing["dob"],
            "gender": gender if gender is not None else existing["gender"],
            "history": history if history is not None else existing["history"],
            "allergies": allergies if allergies is not None else existing["allergies"],
            "medications": medications if medications is not None else existing["medications"]
        }

        conn.execute("""
            UPDATE patients

            SET
                name = ?,
                dob = ?,
                gender = ?,
                history = ?,
                allergies = ?,
                medications = ?,
                updated_at = ?

            WHERE id = ?
        """, (
            values["name"],
            values["dob"],
            values["gender"],
            values["history"],
            values["allergies"],
            values["medications"],
            datetime.now().isoformat(),
            patient_id
        ))

        _write_audit_log(
            conn,
            action="PATIENT_RECORD_UPDATED",
            patient_id=patient_id,
            performed_by=performed_by
        )


# =========================================================
# PATIENT CONSULTATION HISTORY
# =========================================================

def get_patient_consultations(patient_id):

    with get_connection() as conn:

        rows = conn.execute("""
            SELECT *
            FROM consultations

            WHERE patient_id = ?

            ORDER BY date DESC
        """, (patient_id,)).fetchall()

        results = [dict(row) for row in rows]

        for consultation in results:

            _decode_consultation_json(consultation)

        return results


def get_consultation(consultation_id):

    with get_connection() as conn:

        row = conn.execute("""
            SELECT *
            FROM consultations
            WHERE id = ?
        """, (consultation_id,)).fetchone()

        if not row:
            return None

        consultation = dict(row)

        _decode_consultation_json(consultation)

        return consultation


def get_recent_consultations(limit=10):

    with get_connection() as conn:

        rows = conn.execute("""
            SELECT
                c.*,
                p.name AS patient_name

            FROM consultations c

            JOIN patients p
                ON p.id = c.patient_id

            ORDER BY c.date DESC

            LIMIT ?
        """, (limit,)).fetchall()

        results = [dict(row) for row in rows]

        for consultation in results:

            _decode_consultation_json(consultation)

        return results


def _decode_consultation_json(consultation):

    for field in get_json_fields():

        consultation[field] = deserialize_json(
            consultation.get(field),
            default=[]
        )

    return consultation


# =========================================================
# SAVE CONSULTATION
# =========================================================

def save_consultation(
    patient_id,
    transcript,
    soap_dict,
    doctor_name=DEFAULT_DOCTOR_NAME,
    status="Draft",
    consultation_type="General"
):

    if not isinstance(soap_dict, dict):

        raise ValueError(
            "Clinical documentation must be a dictionary."
        )

    now = datetime.now().isoformat()

    doctor_name = (
        doctor_name.strip()
        if doctor_name and doctor_name.strip()
        else DEFAULT_DOCTOR_NAME
    )

    json_fields = get_json_fields()

    with get_connection() as conn:

        patient = conn.execute("""
            SELECT id
            FROM patients
            WHERE id = ?
        """, (patient_id,)).fetchone()

        if not patient:

            raise ValueError(
                "Cannot save consultation: patient not found."
            )

        columns = [

            "patient_id",
            "date",
            "transcript",

            "subjective",
            "objective",
            "assessment",
            "plan",

            "status",
            "doctor_name",
            "consultation_type",

            "chief_complaint",
            "clinical_summary",

            "relevant_history",
            "current_medications_summary",
            "allergies_summary",

            "risk_level",
            "ai_insights",

            "discovered_history",
            "discovered_medications",

            "updated_at"
        ] + json_fields

        values = [

            patient_id,
            now,
            transcript or "",

            soap_dict.get("subjective", ""),
            soap_dict.get("objective", ""),
            soap_dict.get("assessment", ""),
            soap_dict.get("plan", ""),

            status,
            doctor_name,
            consultation_type,

            soap_dict.get("chief_complaint", ""),
            soap_dict.get("clinical_summary", ""),

            soap_dict.get("relevant_history", ""),
            soap_dict.get("current_medications_summary", ""),
            soap_dict.get("allergies_summary", ""),

            soap_dict.get("risk_level", "Not Assessed"),
            soap_dict.get("ai_insights", ""),

            soap_dict.get("discovered_history", ""),
            soap_dict.get("discovered_medications", ""),

            now
        ]

        for field in json_fields:

            values.append(
                serialize_json(
                    soap_dict.get(field, [])
                )
            )

        placeholders = ", ".join(
            ["?"] * len(columns)
        )

        column_string = ", ".join(columns)

        cursor = conn.execute(
            f"""
            INSERT INTO consultations ({column_string})
            VALUES ({placeholders})
            """,
            values
        )

        consultation_id = cursor.lastrowid

        _write_audit_log(
            conn,
            action="CONSULTATION_CREATED",
            patient_id=patient_id,
            consultation_id=consultation_id,
            performed_by=doctor_name,
            details=f"Consultation created with status: {status}"
        )

        return consultation_id


# =========================================================
# UPDATE CONSULTATION DOCUMENTATION
# =========================================================

def update_consultation_documentation(
    consultation_id,
    documentation,
    transcript=None,
    performed_by=DEFAULT_DOCTOR_NAME
):

    if not isinstance(documentation, dict):

        raise ValueError(
            "Documentation must be a dictionary."
        )

    with get_connection() as conn:

        existing = conn.execute("""
            SELECT patient_id, status
            FROM consultations
            WHERE id = ?
        """, (consultation_id,)).fetchone()

        if not existing:

            raise ValueError(
                "Consultation not found."
            )

        if existing["status"] == "Approved":

            raise ValueError(
                "Approved consultations cannot be modified directly. "
                "Create a correction or amendment workflow instead."
            )

        fields = {

            "subjective": documentation.get("subjective", ""),
            "objective": documentation.get("objective", ""),
            "assessment": documentation.get("assessment", ""),
            "plan": documentation.get("plan", ""),

            "chief_complaint": documentation.get("chief_complaint", ""),
            "clinical_summary": documentation.get("clinical_summary", ""),

            "relevant_history": documentation.get("relevant_history", ""),
            "current_medications_summary": documentation.get("current_medications_summary", ""),
            "allergies_summary": documentation.get("allergies_summary", ""),

            "risk_level": documentation.get("risk_level", "Not Assessed"),
            "ai_insights": documentation.get("ai_insights", ""),

            "discovered_history": documentation.get("discovered_history", ""),
            "discovered_medications": documentation.get("discovered_medications", "")
        }

        for field in get_json_fields():

            fields[field] = serialize_json(
                documentation.get(field, [])
            )

        if transcript is not None:

            fields["transcript"] = transcript

        fields["updated_at"] = datetime.now().isoformat()

        assignments = ", ".join(
            f"{column} = ?" for column in fields
        )

        values = list(fields.values())

        values.append(consultation_id)

        conn.execute(
            f"""
            UPDATE consultations
            SET {assignments}
            WHERE id = ?
            """,
            values
        )

        _write_audit_log(
            conn,
            action="CONSULTATION_DOCUMENTATION_UPDATED",
            patient_id=existing["patient_id"],
            consultation_id=consultation_id,
            performed_by=performed_by
        )


# =========================================================
# PATIENT CLINICAL RECORD UPDATES
# =========================================================

def _append_unique(existing, new_value):

    existing = existing or ""

    if not new_value:
        return existing

    new_value = str(new_value).strip()

    if new_value.lower() in {
        "",
        "none",
        "unknown",
        "not documented",
        "not available"
    }:
        return existing

    existing_entries = [
        item.strip().lower()
        for item in existing.splitlines()
        if item.strip()
    ]

    if new_value.lower() in existing_entries:
        return existing

    if existing.strip():

        return (
            existing.rstrip()
            + "\n"
            + new_value
        )

    return new_value


def append_patient_clinical_updates(
    patient_id,
    new_history=None,
    new_meds=None
):

    with get_connection() as conn:

        patient = conn.execute("""
            SELECT history, medications
            FROM patients
            WHERE id = ?
        """, (patient_id,)).fetchone()

        if not patient:

            raise ValueError(
                "Patient not found."
            )

        updated_history = _append_unique(
            patient["history"],
            new_history
        )

        updated_medications = _append_unique(
            patient["medications"],
            new_meds
        )

        conn.execute("""
            UPDATE patients

            SET
                history = ?,
                medications = ?,
                updated_at = ?

            WHERE id = ?
        """, (
            updated_history,
            updated_medications,
            datetime.now().isoformat(),
            patient_id
        ))


# =========================================================
# PHYSICIAN APPROVAL
# =========================================================

def approve_consultation(
    consultation_id,
    performed_by=DEFAULT_DOCTOR_NAME
):
    """
    Approves a consultation and updates the patient's
    longitudinal medical record.

    Only new history and explicitly disclosed long-term
    medications are added automatically.

    Proposed treatments are NOT added to existing
    patient medications.
    """

    with get_connection() as conn:

        consultation = conn.execute("""
            SELECT *
            FROM consultations
            WHERE id = ?
        """, (consultation_id,)).fetchone()

        if not consultation:

            raise ValueError(
                "Consultation not found."
            )

        if consultation["status"] == "Approved":

            raise ValueError(
                "This consultation is already approved."
            )

        patient_id = consultation["patient_id"]

        patient = conn.execute("""
            SELECT *
            FROM patients
            WHERE id = ?
        """, (patient_id,)).fetchone()

        if not patient:

            raise ValueError(
                "Associated patient record not found."
            )

        # Add only explicitly discovered history.
        history = _append_unique(
            patient["history"],
            consultation["discovered_history"]
        )

        # Add only explicitly discovered long-term medication.
        medications = _append_unique(
            patient["medications"],
            consultation["discovered_medications"]
        )

        now = datetime.now().isoformat()

        conn.execute("""
            UPDATE patients

            SET
                history = ?,
                medications = ?,
                updated_at = ?

            WHERE id = ?
        """, (
            history,
            medications,
            now,
            patient_id
        ))

        conn.execute("""
            UPDATE consultations

            SET
                status = 'Approved',
                approved_at = ?,
                updated_at = ?

            WHERE id = ?
        """, (
            now,
            now,
            consultation_id
        ))

        _write_audit_log(
            conn,
            action="CONSULTATION_APPROVED",
            patient_id=patient_id,
            consultation_id=consultation_id,
            performed_by=performed_by,
            details=(
                "Consultation approved. "
                "Eligible patient history updates applied."
            )
        )

        return True


# =========================================================
# PDF ASSOCIATION
# =========================================================

def set_consultation_pdf(
    consultation_id,
    pdf_path,
    performed_by=DEFAULT_DOCTOR_NAME
):

    with get_connection() as conn:

        consultation = conn.execute("""
            SELECT patient_id
            FROM consultations
            WHERE id = ?
        """, (consultation_id,)).fetchone()

        if not consultation:

            raise ValueError(
                "Consultation not found."
            )

        conn.execute("""
            UPDATE consultations

            SET
                pdf_path = ?,
                updated_at = ?

            WHERE id = ?
        """, (
            pdf_path,
            datetime.now().isoformat(),
            consultation_id
        ))

        _write_audit_log(
            conn,
            action="PDF_REPORT_GENERATED",
            patient_id=consultation["patient_id"],
            consultation_id=consultation_id,
            performed_by=performed_by,
            details="Clinical PDF associated with consultation."
        )


# =========================================================
# DELETE PATIENT
# =========================================================

def delete_patient(patient_id):

    with get_connection() as conn:

        patient = conn.execute("""
            SELECT id
            FROM patients
            WHERE id = ?
        """, (patient_id,)).fetchone()

        if not patient:
            return False

        _write_audit_log(
            conn,
            action="PATIENT_DELETED",
            patient_id=patient_id,
            details="Patient record and associated consultations deleted."
        )

        conn.execute("""
            DELETE FROM consultations
            WHERE patient_id = ?
        """, (patient_id,))

        conn.execute("""
            DELETE FROM patients
            WHERE id = ?
        """, (patient_id,))

        return True


# =========================================================
# DASHBOARD STATISTICS
# =========================================================

def get_dashboard_stats():

    with get_connection() as conn:

        patients = conn.execute("""
            SELECT COUNT(*)
            FROM patients
        """).fetchone()[0]

        consultations = conn.execute("""
            SELECT COUNT(*)
            FROM consultations
        """).fetchone()[0]

        today = datetime.now().date().isoformat()

        today_consultations = conn.execute(
    """
    SELECT COUNT(*)
    FROM consultations
    WHERE date LIKE ?
    """,
    (today + "%",)
).fetchone()[0]

        pending = conn.execute("""
            SELECT COUNT(*)
            FROM consultations
            WHERE status = 'Draft'
        """).fetchone()[0]

        approved = conn.execute("""
            SELECT COUNT(*)
            FROM consultations
            WHERE status = 'Approved'
        """).fetchone()[0]

        recent = conn.execute("""
            SELECT
                c.id,
                c.date,
                c.status,
                c.doctor_name,
                p.name,
                p.id AS patient_id

            FROM consultations c

            JOIN patients p
                ON p.id = c.patient_id

            ORDER BY c.date DESC

            LIMIT 5
        """).fetchall()

        return {

            "patients": patients,

            "consultations": consultations,

            "today": today_consultations,

            "pending": pending,

            "approved": approved,

            "recent": [
                dict(row)
                for row in recent
            ]
        }


# =========================================================
# DATABASE HEALTH CHECK
# =========================================================

def database_health_check():

    try:

        with get_connection() as conn:

            conn.execute(
                "SELECT 1"
            ).fetchone()

            tables = conn.execute("""
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
            """).fetchall()

            return {

                "status": "Connected",

                "database": DB_NAME,

                "tables": [
                    row["name"]
                    for row in tables
                ]
            }

    except Exception as e:

        return {

            "status": "Error",

            "message": str(e)
        }
