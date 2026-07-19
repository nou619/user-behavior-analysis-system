import getpass
import os
import sys

sys.path.insert(0, "functions")

os.environ["BREVO_API_KEY"] = getpass.getpass("Paste Brevo API key: ")
os.environ["BREVO_SENDER_EMAIL"] = input(
    "Brevo verified sender email: "
).strip()
os.environ["BREVO_SENDER_NAME"] = "QCMed Alert System"

from services.email import send_email
from weasyprint import HTML

pdf_bytes = HTML(
    string="""
    <html>
      <body>
        <h1>QCMed Brevo Test</h1>
        <p>Le PDF fonctionne correctement.</p>
      </body>
    </html>
    """
).write_pdf()

interactive_html = b"""
<!DOCTYPE html>
<html>
<body>
    <h1>QCMed Interactive Test</h1>
    <p>Le fichier HTML fonctionne correctement.</p>
</body>
</html>
"""

send_email(
    to=["nourbenhnia619@gmail.com"],
    subject="QCMed - Test Brevo",
    body="Test Brevo avec un PDF et un fichier HTML.",
    is_html=False,
    attachments=[
        ("QCMed_Test.pdf", pdf_bytes, "application/pdf"),
        ("QCMed_Test.html", interactive_html, "text/html"),
    ],
)

print("TEST SUCCESSFUL")
