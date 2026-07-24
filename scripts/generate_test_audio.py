"""
generate_test_audio.py — Generate synthetic test audio files using Google Text-to-Speech (gTTS)
for testing the DocTel transcription and RAG pipeline.

Produces MP3 files with ZETDC domain content:
  1. OMS Discussion (meeting scenario)
  2. Billing System Overview (presentation)
  3. ZUMS Mobile Features (product demo)
  4. Customer Service Script (call center)
  5. NDPM Workflow (technical process)

Usage:
    python scripts/generate_test_audio.py

Output:
    localai/data/test_audio/*.mp3
"""

import os
import sys
from pathlib import Path

# Ensure we can import from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gtts import gTTS
from datetime import datetime


# ── Output directory ──────────────────────────────────────────────────────────
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "localai" / "data" / "test_audio"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# TTS options
TTS_LANG = "en"
TTS_TLD = "co.za"  # South African accent — closer to Zimbabwean English
TTS_SLOW = False


# ── Test scripts ──────────────────────────────────────────────────────────────

SCENARIOS = [
    {
        "filename": "oms_discussion.mp3",
        "title": "OMS — Outage Management System Discussion",
        "text": """
Good morning everyone. Today we are discussing the implementation of the Outage Management System, or OMS, for ZETDC.

The OMS will replace our current manual outage tracking process. Currently, when a customer reports an outage, the call centre agent logs it in an Excel spreadsheet. The dispatcher then manually assigns a crew. There is no real-time visibility of outage status.

The new OMS will automate this entire workflow. When a customer calls, the system will automatically create a trouble ticket. The dispatcher will see all active outages on a map-based dashboard. Crews will be assigned automatically based on location and availability.

The key benefits include reduced outage duration, improved customer communication, and better data for analysis. We expect to reduce the average outage duration from 4 hours to under 2 hours within the first year of deployment.

The implementation timeline is as follows. Phase one, system configuration and integration with CRM, will take three months. Phase two, user acceptance testing, will take one month. Phase three, go-live and training, will take two weeks.

We need to ensure integration with the Customer Relationship Management system, the Geographic Information System, and the mobile app for field crews. The project team will meet weekly to track progress.

Are there any questions about the OMS implementation?
""".strip(),
    },
    {
        "filename": "billing_system_overview.mp3",
        "title": "Billing System — FRS Overview",
        "text": """
Welcome to this overview of the ZETDC Billing System Functional Requirements Specification.

The billing system is the core financial system for ZETDC. It handles customer billing, payment processing, meter management, and revenue collection. The system currently serves over six hundred thousand customers across Zimbabwe.

The key modules include customer management, meter reading, billing calculation, payment processing, credit management, and reporting.

For customer management, the system maintains a complete customer register with contact details, service addresses, meter information, and billing history. New connections are processed through the New Connections module.

For meter reading, the system supports both manual and automated meter reading. Field workers can record readings using the mobile app. The readings are validated against historical consumption patterns before being used for billing.

For billing calculation, the system applies the approved tariff structure. Residential customers are billed on a tiered tariff. Commercial and industrial customers have time-of-use tariffs. The billing engine calculates charges, taxes, and any applicable discounts or penalties.

For payment processing, the system supports multiple payment channels including EcoCash, bank transfers, point of sale terminals, and direct debit. Payments are matched to customer accounts in real-time.

The system also includes a credit management module that tracks outstanding balances, generates payment reminders, and manages disconnection and reconnection workflows.

This concludes the billing system overview. Thank you.
""".strip(),
    },
    {
        "filename": "zums_mobile_features.mp3",
        "title": "ZUMS Mobile — Features and Functionality",
        "text": """
Hello and welcome to the ZUMS Mobile demonstration.

ZUMS Mobile, also known as the Field Worker Application or FWA, is the mobile component of the ZETDC Billing System. It is designed for field workers who need to access the system while working in the field.

The application supports several key functions. First, the My To-do function. This displays all tasks assigned to the field worker. Tasks include new connection inspections, meter reading assignments, disconnection orders, and fault investigations.

Second, the My Application function. This shows all applications submitted by the field worker, including new connection requests and meter change requests.

Third, the My Message function. This provides messaging and notification capabilities. Field workers receive announcements, task assignments, and alerts through this function.

Fourth, the Customer Lookup function. Field workers can search for customer information by account number, meter number, or name. This provides access to customer contact details, service address, and billing history.

Fifth, the Job Management function. This allows field workers to accept, start, and complete assigned jobs. Each job includes instructions, customer details, and any relevant documentation.

The application works offline. When the field worker has network connectivity, data synchronises automatically with the central system. This ensures that field workers can continue working even in areas with poor network coverage.

All communication is encrypted using industry standard protocols. User access is controlled through role-based permissions configured by the system administrator.

This concludes the ZUMS Mobile overview. Thank you for your attention.
""".strip(),
    },
    {
        "filename": "customer_service_script.mp3",
        "title": "Customer Service — Call Handling Script",
        "text": """
This is a standard call handling script for ZETDC customer service representatives.

When you receive a call, begin with the following greeting. Good day, thank you for calling ZETDC customer service. My name is representative name. How may I assist you today?

Listen to the customer's query without interrupting. Identify whether the query is a fault report, a billing enquiry, a new connection request, or a general enquiry.

For fault reports, ask the following questions. What is your account number or meter number? What is the nature of the fault? Is there a power outage in your area? When did the fault start? Have you reported this before?

Enter the details into the Outage Management System. If it is a new fault, create a trouble ticket. If it is a known outage, inform the customer of the estimated restoration time.

For billing enquiries, ask for the account number. Review the customer's billing history. Explain any charges that the customer does not understand. If there is a billing dispute, create a billing enquiry ticket for the billing department to investigate.

For new connection requests, explain the application process. The customer needs to complete a new connection application form and provide identification documents. The connection fee must be paid before the inspection is scheduled.

Always remain professional and courteous. If you cannot resolve the query, escalate to a supervisor. Never make promises that you cannot deliver. Always confirm the customer's contact details before ending the call.

End every call with the following closing. Thank you for calling ZETDC. Have a good day.
""".strip(),
    },
    {
        "filename": "ndpm_workflow.mp3",
        "title": "NDPM — New Connections Process Workflow",
        "text": """
This document describes the New Connections process within the ZETDC New Connections and Project Management module, known as NDPM.

The new connections process begins when a customer submits an application for a new electricity connection. The application can be submitted at any ZETDC customer service centre or through the online portal.

Upon receipt, the application is logged in the NDPM system and assigned a unique application reference number. The system checks that all required documentation has been provided. If documentation is incomplete, the application is returned to the customer with a list of missing items.

Once the application is complete, a site inspection is scheduled. The inspection is assigned to a qualified technician. The technician visits the site to assess the technical requirements for the connection. This includes determining the distance from the nearest distribution line, the required transformer capacity, and any special installation requirements.

The technician completes an inspection report in the NDPM mobile application. The report includes photographs, GPS coordinates, and a recommendation. The system automatically calculates the estimated connection cost based on the inspection data.

The customer is notified of the estimated cost and timeline. Once the customer accepts the quotation and makes payment, the connection work is scheduled. The system assigns the job to a construction crew.

The crew completes the connection work and updates the job status in the NDPM mobile application. A final inspection is conducted to verify that the installation meets ZETDC standards. The meter is installed and the customer account is activated.

The entire process from application to activation typically takes five to ten working days for standard connections. Complex connections may take longer depending on the technical requirements.

This concludes the NDPM new connections workflow description.
""".strip(),
    },
    {
        "filename": "shona_conversation.mp3",
        "title": "Conversation in Shona — Customer Query",
        "text": """
Mhoro, ndinoda kubvunza nezve account yangu yemagetsi. Ini ndinonzi Tatenda Mukono, account number yangu ndeye one two three four five six.

Ndirikunzwa kuti bhiri rangu rakawedzera zvakanyanya mwedzi uno. Ndinoda kuti munditsanangurire kuti chii chaitika.

Ndinotenda nekufona, vaMukono. Ndichaongorora account yenyu. Ndirikuona kuti bhiri rako rakawedzera nekuti mvura yakawanda yanaya, saka magetsi akawanda akashandiswa. Zvakare, tariff yakwira zvishoma kubva muna January.

Handina kuziva kuti tariff yakwira. Ndinoda kuti mundinyatso tsanangurirawo mituro iyi.

Zvakanaka. Iyo tariff yemagetsi ine zvikamu zvinomwe. Chikamu chekutanga, mapaOne hundred kilowatt hours ekutanga, anobhadharwa mashanu emadola pa kilowatt hour. Kana ukashandisa magetsi akawanda, mutengo unokwira.

Ndinonzwisisa. Ndinokutendai nerubatsiro. Ndichaita mari yangu kuti ndibhadhare bhiri iri panguva yacho.

Tatenda, vaMukono. Kana mumwe mubvunzo uine, fonai zvakare. Kwete.
""".strip(),
    },
]


# ── Generation ────────────────────────────────────────────────────────────────

def generate_audio(text: str, output_path: Path, lang: str = TTS_LANG, tld: str = TTS_TLD) -> bool:
    """Generate MP3 from text using gTTS."""
    try:
        tts = gTTS(text=text, lang=lang, tld=tld, slow=TTS_SLOW)
        tts.save(str(output_path))
        size_kb = output_path.stat().st_size / 1024
        print(f"  [OK] {output_path.name} - {size_kb:.0f} KB")
        return True
    except Exception as e:
        print(f"  [FAIL] {output_path.name} - FAILED: {e}")
        return False


def main():
    print("=" * 60)
    print("  DocTel Test Audio Generator")
    print(f"  Output: {OUTPUT_DIR}")
    print(f"  TTS:    gTTS (lang={TTS_LANG}, tld={TTS_TLD})")
    print(f"  Date:   {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)
    print()

    success_count = 0
    for scenario in SCENARIOS:
        print(f"[{scenario['title']}]")
        output_path = OUTPUT_DIR / scenario["filename"]
        if generate_audio(scenario["text"], output_path):
            success_count += 1
        print()

    # ── Summary ─────────────────────────────────────────────────────────────
    total = len(SCENARIOS)
    total_size_kb = sum(
        f.stat().st_size for f in OUTPUT_DIR.glob("*.mp3") if f.is_file()
    ) / 1024

    print("=" * 60)
    print(f"  Generated: {success_count}/{total} files")
    print(f"  Total size: {total_size_kb:.0f} KB")
    print(f"  Location: {OUTPUT_DIR}")
    print()
    print("  Files:")
    for f in sorted(OUTPUT_DIR.glob("*.mp3")):
        kb = f.stat().st_size / 1024
        print(f"    + {f.name} ({kb:.0f} KB)")
    print("=" * 60)


if __name__ == "__main__":
    main()
