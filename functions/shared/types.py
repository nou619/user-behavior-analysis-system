from dataclasses import dataclass

@dataclass
class Alert:
    id: str
    student_nom: str
    student_prenom: str
    question_id: str
    question_description: str
    matiere: str
    cours: str
    niveau: str
    faculte: str
    alert_type: str
    status: str
    details: str
    created_at: str

@dataclass
class SheetAlert:
    alert_id: str
    created_at: str
    updated_at: str
    status: str
    alert_type: str
    details: str
    user_fullname: str
    user_email: str
    user_niveau: str
    user_faculte: str
    question_description: str
    question_responses: str
    question_correct_response: str
    cours_title: str
    matiere_title: str
    certif_title: str
    certif_niveau: str
    certif_faculte: str
    question_times_answered: int

@dataclass
class User:
    id: str
    nom: str
    prenom: str
    email: str
    role: str
    faculte: str
    niveau: str
    study_time_seconds: int
    questions_practiced: int
    correct_answers: int
    success_rate: float
    completed_courses: int
    viewed_flashcards: int
    current_streak: int
    last_session_start: str
    created_at: str

@dataclass
class LeaderboardEntry:
    export_date: str
    category: str
    rank: int
    user_fullname: str
    faculte: str
    niveau: str
    value: int

@dataclass
class OverviewStats:
    export_date: str
    total_students: int
    active_this_week: int
    inactive: int
    new_this_week: int
    count_fmm: int
    count_fmt: int
    count_fmsf: int
    count_fmso: int