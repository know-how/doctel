# Mobile App Quick Start Guide

## 🚀 Getting Started

### First Time Setup
1. **Open the app** → You'll see the login screen
2. **Choose authentication method:**
   - **EC + Password:** Enter your EC number and password
   - **ZETDC Email:** Enter your ZETDC email and wait for OTP code
3. **Sign in** → You're now authenticated and ready to use all features

### Main Navigation Tabs (After Login)

| Tab | Icon | Function |
|-----|------|----------|
| 📚 Library | Main screen | Upload new documents, home page |
| 💬 Chat | Chat bubble | Chat with a specific document |
| 🌍 Global | Globe | Chat across all your documents |
| 🤖 Models | Robot | Manage AI models (download/select) |
| 📁 Projects | Folder | Browse your projects and documents |
| 📋 Sessions | List | View and manage chat conversations |
| 🔧 Status | Wrench | Check system health and bootstrap |
| ⬆️ Upload | Upload arrow | Upload new documents |

---

## 📄 Document Operations

### Upload a Document
1. Tap **⬆️ Upload** tab
2. Select a document file from your device
3. **(Optional)** Fill in metadata:
   - Document type (e.g., Memo, Report, Policy)
   - Document date
   - Project (create new or select existing)
4. Tap **"Upload"** button
5. Wait for upload to complete
6. Automatically switches to **💬 Chat** tab with new document

### Chat with a Document
1. Tap **💬 Chat** tab (or document opens automatically after upload)
2. View the document's:
   - Summary and key information
   - Suggested questions (from AI)
   - Analysis and key entities
3. Type your question in the input field
4. Tap **"Send"** button
5. Wait for AI response
6. View answer with source citations and page references

### Download a Document
1. In **💬 Chat** tab, look for download button
2. File saves to your device's Downloads folder
3. You can share or view the original document

### Document Analysis
- **Executive Summary:** Key points and overview
- **Entities:** Important people, places, organizations mentioned
- **Topics:** Main subjects covered
- **Sentiment:** Overall tone of document
- **Action Items:** Required tasks or decisions

---

## 💬 Chat Features

### Document-Specific Chat
1. Tap **💬 Chat** tab
2. Ask questions about the document
3. Get answers with source citations
4. Sources show which part of document the answer came from

### Global Chat (Across All Documents)
1. Tap **🌍 Global** tab
2. Select a model from the model selector at top
3. Ask questions about any topic
4. AI will search across all your documents
5. Answers include which documents were referenced

### Chat Sessions
1. Tap **📋 Sessions** tab to see all conversations
2. **View a session:** Tap on any session to continue chatting
3. **Start new session:** Tap "**+ New Chat Session**" button
4. **Delete session:** Swipe left or use delete button (if available)
5. **Manage sessions:** See message count, creation date

### Model Selection
- **For document chat:** Model is set per session (can change)
- **For global chat:** Select model before asking questions
- **Change model:** In **🤖 Models** tab or during chat

---

## 🤖 Model Management

### View Available Models
1. Tap **🤖 Models** tab
2. See list of available models with status:
   - ✓ **Ready** - Available to use immediately
   - ⬇ **Downloading** - Currently being downloaded
   - ✗ **Failed** - Download failed, tap Retry

### Download a New Model
1. Tap **🤖 Models** tab
2. Find a model with status **"✗ Failed"** or unavailable
3. Tap **"Retry"** or download button
4. Monitor progress bar as model downloads
5. Once complete, model shows **"✓ Ready"**

### Use a Model
1. Tap **🤖 Models** tab
2. Select a model with **"✓ Ready"** status
3. Tap **"Select"** button
4. Model is now active for your chats

---

## 📁 Project Management

### View Projects
1. Tap **📁 Projects** tab
2. See all your projects with document counts
3. **Create new project:** Tap **"+ New Project"** button
4. **View project details:** Tap on a project

### Within a Project
- See all documents in the project
- Quick access to chat with any document
- View document metadata (type, date, size)
- Browse through all project documents

### Manage Projects
- **Move document to project:** Upload and assign to project
- **View project analysis:** Combined insights from all documents
- **Filter by project:** When browsing documents

---

## 🔧 System Status

### Check System Health
1. Tap **🔧 Status** tab
2. View current system status:

| Component | Status | Meaning |
|-----------|--------|---------|
| 🔧 Bootstrap | ✓ Ready | System is fully initialized |
| 🤖 Models | ✓ Ready | AI models are loaded |
| 📚 Vector Store | ✓ Ready | Search database is ready |

### Troubleshoot Issues
- If any component shows ⏳ **Pending:**
  - System is still initializing
  - Wait a few moments and refresh
  - Try logging out and back in

- If any component shows ✗ **Failed:**
  - Check backend server status
  - Restart the app
  - Contact administrator if issue persists

### Pull-to-Refresh
- Swipe down on status screen to manually refresh

---

## ⚙️ Settings & Account

### Logout
1. Tap the **"Logout"** button in top-right corner of header
2. You'll return to login screen
3. All session data is saved (you can log back in anytime)

### Change Model for Chat Session
1. During a chat, look for model selector
2. Swipe left/right through available models
3. Tap model name to select it
4. Next response will use new model

### Storage & Offline
- 📱 **Local Storage:** Auth token stored safely on device
- ⚠️ **Note:** App requires internet connection to function
- 🔄 **Auto-Save:** All chat history synced with backend

---

## 🆘 Troubleshooting

### Login Issues
**"Unable to reach backend"**
- ✅ Check internet connection
- ✅ Verify backend server is running
- ✅ Check if API URL is correct (ask admin)

**"Invalid EC number or password"**
- ✅ Verify spelling and case sensitivity
- ✅ Reset password through admin portal
- ✅ Try email login as alternative

**"Email OTP not received"**
- ✅ Check spam/junk folder
- ✅ Wait up to 2 minutes for email delivery
- ✅ Try requesting code again
- ✅ Use EC + Password login instead

### Chat Issues
**"Failed to get answer"**
- ✅ Check internet connection
- ✅ Try again in a few moments
- ✅ Switch to different model
- ✅ Check system status (🔧 tab)

**"Document ingestion pending"**
- ✅ Wait for document to complete ingestion
- ✅ Large documents take longer (5-15 minutes)
- ✅ Check 📋 Sessions or 🔧 Status for progress
- ✅ App will automatically retry when ready

**"Model download failed"**
- ✅ Check available storage space
- ✅ Ensure stable internet connection
- ✅ Try downloading a different model first
- ✅ Tap **Retry** button to resume

### Session Lost
**"Session expired. Please sign in again"**
- ✅ Your session timed out for security
- ✅ Log in again with your credentials
- ✅ All chat history is preserved
- ✅ You can resume previous conversations

---

## 💡 Tips & Tricks

### Asking Better Questions
- ❌ "Summarize this" (too vague)
- ✅ "What are the key findings in section 2?"

- ❌ "What's in this?"
- ✅ "List all financial recommendations with amounts"

- ❌ "More info"
- ✅ "How does this affect our compliance requirements?"

### Document Organization
- 📁 Use projects to group related documents
- 🏷️ Add document type when uploading for easier filtering
- 📅 Include document date for chronological sorting

### Managing Sessions
- 💬 Create separate sessions for different topics
- 🔄 Switch between sessions to maintain conversation context
- 🗑️ Delete old sessions to keep workspace clean

### Performance
- 📊 Large documents (100+ pages) take longer to process
- 📱 Close other apps for faster performance
- 🔋 Keep device plugged in for long sessions

---

## 📞 Need Help?

- **Technical Issues:** Contact your IT administrator
- **Forgotten Password:** Use password reset link in login screen
- **Feature Requests:** Ask administrator to submit feedback
- **Security Issues:** Report immediately to IT security team

---

**Version:** 1.0.0  
**Last Updated:** April 17, 2026  
**Status:** ✅ Complete and Ready to Use
