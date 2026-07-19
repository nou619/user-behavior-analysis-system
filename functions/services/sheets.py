import os
import gspread
from google.oauth2.service_account import Credentials
from shared.types import SheetAlert, LeaderboardEntry, OverviewStats

def get_client() -> gspread.Client:
    creds = Credentials.from_service_account_file(
        os.environ["SERVICE_ACCOUNT_FILE"],
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
    )
    return gspread.authorize(creds)

def load_worksheet_records(tab_name: str) -> list[dict]:
    gc = get_client()
    ws = gc.open_by_key(os.environ["SHEET_ID"]).worksheet(tab_name)
    return ws.get_all_records()

def load_sheet() -> list[SheetAlert]:
    records = load_worksheet_records(os.environ["SHEET_TAB"])

    alerts = []
    for row in records:
        try:
            alert = SheetAlert(
                alert_id=str(row.get("alert_id", "")),
                created_at=str(row.get("created_at", "")),
                updated_at=str(row.get("updated_at", "")),
                status=str(row.get("status", "")),
                alert_type=str(row.get("alert_type", "")),
                details=str(row.get("details", "")),
                user_fullname=str(row.get("user_fullname", "")),
                user_email=str(row.get("user_email", "")),
                user_niveau=str(row.get("user_niveau", "")),
                user_faculte=str(row.get("user_faculte", "")),
                question_description=str(row.get("question_description", "")),
                question_responses=str(row.get("question_responses", "")),
                question_correct_response=str(row.get("question_correct_response", "")),
                cours_title=str(row.get("cours_title", "")),
                matiere_title=str(row.get("matiere_title", "")),
                certif_title=str(row.get("certif_title", "")),
                certif_niveau=str(row.get("certif_niveau", "")),
                certif_faculte=str(row.get("certif_faculte", "")),
                question_times_answered=int(row.get("question_times_answered", 0) or 0)
            )
            alerts.append(alert)
        except Exception as e:
            print(f"Skipping malformed row: {e}")
            continue
    return alerts

def load_leaderboards() -> list[LeaderboardEntry]:
    records = load_worksheet_records("Stats_Leaderboards")

    entries = []
    for row in records:
        try:
            entry = LeaderboardEntry(
                export_date=str(row.get("export_date", "")),
                category=str(row.get("category", "")),
                rank=int(row.get("rank", 0) or 0),
                user_fullname=str(row.get("user_fullname", "")),
                faculte=str(row.get("faculte", "")),
                niveau=str(row.get("niveau", "")),
                value=int(row.get("value", 0) or 0)
            )
            entries.append(entry)
        except Exception as e:
            print(f"Skipping malformed leaderboard row: {e}")
            continue
    return entries

def load_overview() -> OverviewStats:
    records = load_worksheet_records("Stats_Overview")

    if not records:
        raise ValueError("Stats_Overview sheet is empty")

    row = records[0]
    return OverviewStats(
        export_date=str(row.get("export_date", "")),
        total_students=int(row.get("total_students", 0) or 0),
        active_this_week=int(row.get("active_this_week", 0) or 0),
        inactive=int(row.get("inactive", 0) or 0),
        new_this_week=int(row.get("new_this_week", 0) or 0),
        count_fmm=int(row.get("count_fmm", 0) or 0),
        count_fmt=int(row.get("count_fmt", 0) or 0),
        count_fmsf=int(row.get("count_fmsf", 0) or 0),
        count_fmso=int(row.get("count_fmso", 0) or 0)
    )