# DocTel Quick Reference Guide

**Version:** 1.0  
**Date:** May 10, 2026  
**Audience:** DocTel Users, First-Time Users

---

## 1. First-Time User Quick Start

### Step 1: Login (30 seconds)
```
1. Navigate to DocTel portal
2. Enter your email address
3. Check email for OTP code
4. Enter OTP code
5. Click "Verify" → Login complete!
```

### Step 2: Explore Dashboard (1 minute)
```
Left Panel:    Your projects (click to filter)
Center:        All documents in project
Top:           Add New Project / Upload Document buttons
Right Panel:   Quick stats and team members
```

### Step 3: Upload Your First Document (2 minutes)
```
1. Click "Upload Document"
2. Select PDF, DOCX, or TXT file
3. Enter/select project
4. Choose document type (optional)
5. Add tags (optional)
6. Click "Upload"
```

### Step 4: Wait for Analysis (30-60 seconds)
```
The system will automatically:
- Extract text from document
- Generate embeddings
- Create summary and analysis
- Generate suggested questions
- Status will change to "Completed"
```

### Step 5: Ask Questions (1 minute)
```
1. Click on completed document
2. See suggested questions on the right
3. Click any question OR type your own
4. View answer with citations
5. Continue asking follow-up questions
```

---

## 2. Key Concepts Explained

### Executive Summary
**What:** A concise 5-10 sentence overview of the document  
**Why:** Understand the entire document in 30 seconds  
**How:** LLM analyzes key sections and creates summary  

### Entities
**What:** Important names, places, dates, concepts mentioned  
**Why:** Quickly identify key stakeholders, locations, deadlines  
**How:** AI extracts from document context  

### Sentiment
**What:** Overall tone of document (Positive/Neutral/Negative/Urgent)  
**Why:** Gauge document urgency and nature  
**How:** LLM classifies document emotion  

### Topics
**What:** Main themes discussed (Infrastructure, Safety, Finance, etc.)  
**Why:** Understand document focus areas  
**How:** LLM identifies and ranks by relevance  

### Suggested Prompts
**What:** 3-5 pre-generated questions tailored to document  
**Why:** Get started immediately without thinking of questions  
**How:** AI generates contextually relevant questions  

### Citations
**What:** References like [Doc: filename, chunk 5]  
**Why:** Verify answer sources, find exact location  
**How:** Link to original document section  

### Project
**What:** Group of related documents  
**Why:** Organize and search across multiple documents  
**How:** Scope queries to specific project  

---

## 3. Common Tasks

### Task: Find a Specific Policy Requirement
```
1. Upload policy document
2. Wait for "Completed" status
3. Click on document
4. In chat, type: "What is the requirement for [topic]?"
5. DocTel returns answer with source citation
6. Click citation to see original text
```

### Task: Compare Information Across Documents
```
1. Create project and upload multiple documents
2. Ensure all are "Completed"
3. Switch to "Project View"
4. Ask: "Compare [topic] across all documents"
5. System searches all documents
6. Returns consolidated answer with multiple citations
```

### Task: Extract Action Items from Meeting Minutes
```
1. Upload meeting minutes PDF
2. Wait for analysis
3. Click document
4. View "Action Items" section in dashboard
5. Each action item shows: Task, Owner, Deadline
6. Ask follow-up questions for clarification
```

### Task: Understand Document at a Glance
```
1. Upload document
2. Wait for analysis
3. On dashboard, see:
   - Executive Summary (quick overview)
   - Sentiment (urgency indicator)
   - Top Topics (main themes)
   - Top Entities (key people/places)
4. Read 2-minute summary instead of document
```

### Task: Share Project with Team Member
```
1. Click on project
2. Click "Team" or "Share"
3. Enter team member email
4. Select their role: Analyst / Viewer
5. They receive access and can ask questions
```

---

## 4. Tips & Tricks

### Tip 1: Ask Specific Questions
**Instead of:** "What's in this document?"  
**Try:** "What are the specific requirements for equipment maintenance?"  
→ More specific = Better answer

### Tip 2: Follow Up with Questions
**First question:** "What are the main topics?"  
**Follow-up:** "Explain the first topic in detail"  
→ Build conversation naturally

### Tip 3: Use Project Context
**Single document:** Limited to that document  
**Project scope:** Searches all related documents  
→ Ask cross-document questions for comprehensive answers

### Tip 4: Leverage Suggested Prompts
**Don't ignore them:** These are pre-optimized questions  
**Click them:** Faster than typing your own  
→ Learn question patterns

### Tip 5: Review Citations
**Always verify:** Click citations to see source  
**Cross-check:** Ensure context matches answer  
→ Build confidence in answers

### Tip 6: Tag Documents Well
**Use meaningful tags:** "Q1-2026", "Safety", "Critical"  
**Search by tags:** Filter documents quickly  
→ Organization saves time later

### Tip 7: Document Types Matter
**Select correct type:** Policy, Report, Minutes, etc.  
**Improves analysis:** System adjusts analysis for document type  
→ Better summaries and questions

---

## 5. Troubleshooting

### Issue: "Analysis Failed" or "Processing Error"
**Cause:** File too large or corrupted  
**Solution:**
1. Download and re-upload file
2. If >100MB, split document first
3. Try different format (PDF instead of DOCX)
4. Contact support if persists

### Issue: Answers Seem Wrong or Off-Topic
**Cause:** Question too vague or document doesn't contain answer  
**Solution:**
1. Rephrase question more specifically
2. Ask different question about same topic
3. Check citations - maybe document doesn't cover topic
4. Try a different document

### Issue: Can't Find Document I Uploaded
**Cause:** Document in different project or not refreshed  
**Solution:**
1. Check project filter (top left)
2. Refresh page (F5)
3. Search document name in search box
4. Check if in "Processing" (wait for completion)

### Issue: Getting Same Answer Repeatedly
**Cause:** System finding same section repeatedly  
**Solution:**
1. Ask more specific question
2. Use different phrasing
3. Ask about different section of document
4. Try follow-up question

### Issue: Login Fails / OTP Not Received
**Cause:** Email filtering or system issue  
**Solution:**
1. Check spam folder for OTP email
2. Try requesting new OTP
3. Wait 1-2 minutes for email to arrive
4. Contact Help Desk if still failing

### Issue: Slow Performance or Long Wait Times
**Cause:** System under load or large document  
**Solution:**
1. Try again during off-peak hours
2. Close unused browser tabs
3. Clear browser cache
4. For large documents, check file isn't corrupted
5. Contact IT if persists

---

## 6. Security & Privacy

### What Happens to My Documents?
- ✅ Stored securely in company database
- ✅ Only you and project members can access
- ✅ Encrypted in transit and at rest
- ✅ Never shared externally
- ✅ Audit logged (who accessed when)

### Data Retention
- Documents kept indefinitely (can delete manually)
- Chat history kept for 1 year
- Backup copies kept for 30 days

### Accessing Your Data
- All your documents listed in dashboard
- Can download original file anytime
- Can delete document (also deletes all analysis)
- Project members see same documents

### Privacy Best Practices
1. Don't upload confidential external documents
2. Be careful with personally identifiable information (PII)
3. Review who has project access
4. Log out when leaving computer
5. Report suspicious activity to IT

---

## 7. Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Cmd/Ctrl + Shift + N` | New Project |
| `Cmd/Ctrl + U` | Upload Document |
| `Cmd/Ctrl + F` | Search Documents |
| `Enter` | Send Question (in chat) |
| `Escape` | Close Dialog |
| `Cmd/Ctrl + K` | Open Command Palette |
| `?` | Help & Shortcuts |

---

## 8. Roles & Permissions

### Administrator
- Manage users and teams
- Configure system settings
- Manage all projects
- View audit logs
- Create/delete projects and documents

### Analyst
- Create projects
- Upload documents
- Ask questions
- Share projects with team
- Cannot manage users or system settings

### Viewer
- View shared projects
- Ask questions about documents
- Cannot upload or create projects
- Read-only access

---

## 9. Common Questions

**Q: Can I upload a document without a project?**  
A: No, all documents must belong to a project. You can create a project called "Inbox" for miscellaneous documents.

**Q: How long does analysis take?**  
A: Typically 30-60 seconds for a 10-page document. Longer documents take proportionally longer.

**Q: Can I edit documents after upload?**  
A: No, but you can delete and re-upload. Edits must be made in original application (Word, Acrobat) first.

**Q: How many documents can I upload?**  
A: Unlimited. System can handle thousands of documents.

**Q: Can questions span multiple documents?**  
A: Only within the same project. Create one project for related documents.

**Q: Are answers always 100% accurate?**  
A: DocTel shows answers from document context (see citations). If document has wrong info, answer may too.

**Q: Can I export the analysis?**  
A: Not yet, but this is planned. Currently, you can screenshot or copy-paste.

**Q: Is DocTel available offline?**  
A: Not currently, but mobile offline support is planned.

---

## 10. Getting Help

### For Technical Issues
- **Email:** doctel-support@zetdc.co.zw
- **Chat:** Internal Slack channel #doctel-support
- **Phone:** IT Help Desk [extension]

### For Training
- **Self-paced:** DocTel Wiki & Documentation
- **Live sessions:** Scheduled bi-weekly training
- **One-on-one:** Request demo with power user

### For Feature Requests
- **Email:** doctel-product@zetdc.co.zw
- **Form:** In-app feedback button
- **Channel:** #doctel-feature-requests

### For Bugs
- **Report in:** #doctel-bugs Slack channel
- **Include:** Screenshot + what you were trying to do
- **Or:** doctel-support@zetdc.co.zw

---

## 11. Key Statistics

- **Processing Time:** 30-60 sec per 10-page document
- **Supported Formats:** PDF, DOCX, TXT
- **Max File Size:** 100 MB
- **Chunk Size:** ~1000 tokens (removable overlap: 200 tokens)
- **Suggested Questions:** 3-5 per document
- **Search Results:** Top 6 relevant chunks returned
- **Chat History:** Unlimited per session
- **Token Expiry:** 24 hours
- **OTP Validity:** 15 minutes

---

## 12. At-A-Glance Interface

```
┌──────────────────────────────────────────────────┐
│  DocTel  [Profile] [Help] [Settings]            │
├──────────────────────────────────────────────────┤
│ Projects │  New Project | Upload Document       │
├──────────┤─────────────────────────────────────┤
│ Project 1│ Doc1.pdf  [Completed] [Open]        │
│ Project 2│ Doc2.docx [Analyzing 67%]           │
│ Project 3│ Doc3.txt  [Uploaded] [Process]      │
└──────────┴─────────────────────────────────────┘

[Open Document - Two Panel Layout]

LEFT PANEL                RIGHT PANEL
─────────────────       ──────────────────
📝 Summary              🔍 Suggested Questions
👥 Entities             💬 Chat Input
😊 Sentiment            💭 Chat History
🏷️ Topics
✅ Action Items
```

---

## 13. Video Tutorial Links

- **Getting Started:** [Link to 5-min intro]
- **Upload & Analyze:** [Link to walkthrough]
- **Ask Questions:** [Link to Q&A demo]
- **Project Features:** [Link to advanced features]
- **Admin Setup:** [Link to admin guide]

---

**Last Updated:** May 10, 2026  
**Next Review:** August 10, 2026

**Questions? Email: doctel-support@zetdc.co.zw**
