# 🚀 Yashraj AI Assistant OS

> Enterprise Generative AI Scheduling Assistant powered by Gemini AI, FastAPI, Google Calendar API, and Intelligent Workflow Automation.

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-green)
![Gemini AI](https://img.shields.io/badge/Gemini-AI-purple)
![React](https://img.shields.io/badge/React-Frontend-61DAFB)
![MySQL](https://img.shields.io/badge/MySQL-Database-orange)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

# 🧠 Overview

Yashraj AI Assistant OS is an enterprise-grade Generative AI productivity platform that transforms natural language into actionable workflows.

The system leverages Large Language Models (LLMs), AI Agent architecture, Google Calendar integration, and intelligent scheduling algorithms to automate productivity tasks such as:

- Meeting Scheduling
- Calendar Management
- Productivity Recommendations
- Note Management
- Conversational AI Assistance
- Workflow Automation

Instead of manually creating events and managing schedules, users interact naturally with an AI assistant.

Example:

```text
Schedule a project presentation tomorrow at 11 AM with Krishna
```

The AI automatically:

- Understands intent
- Extracts participants
- Parses time and date
- Detects conflicts
- Creates calendar events
- Syncs with Google Calendar

---

# 🎯 Key Features

## 🤖 Generative AI Assistant

Natural language conversational interface powered by Gemini AI.

Capabilities:

- Context-aware conversations
- Intent recognition
- Action generation
- Task automation
- Workflow orchestration

---

## 📅 Intelligent Meeting Scheduling

Create meetings using natural language.

Example:

```text
Create a project planning meeting tomorrow from 10 AM to 11 AM
```

Features:

- Calendar conflict detection
- Smart scheduling
- Availability analysis
- Google Calendar synchronization
- Timezone support

---

## 🧠 AI Agent Workflow

The assistant operates as an intelligent AI Agent.

Workflow:

```text
User Prompt
      │
      ▼
Intent Recognition
      │
      ▼
Entity Extraction
      │
      ▼
Action Planning
      │
      ▼
Calendar Execution
      │
      ▼
Response Generation
```

---

## 📝 Notes Management

Store and manage notes directly from the assistant interface.

Examples:

```text
Save note: Complete Gemini integration
```

```text
Remember to submit project report by Friday
```

---

## 📊 Productivity Analytics

Dashboard includes:

- Total Meetings
- Upcoming Meetings
- Productivity Score
- AI Suggestions
- Calendar Health Monitoring

---

# 🔥 Generative AI Architecture

```text
┌─────────────────────────┐
│      User Request       │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│      Gemini AI LLM      │
│ Intent Recognition      │
│ Entity Extraction       │
│ Structured Generation   │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│ Scheduling Intelligence │
│ Conflict Detection      │
│ Availability Analysis   │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│ Action Execution Layer  │
│ Calendar / Notes        │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│ Google Calendar Sync    │
└─────────────────────────┘
```

---

# 🤖 LLM Engineering Concepts

This project demonstrates practical implementation of:

## Prompt Engineering

- Structured prompts
- Intent extraction prompts
- Scheduling prompts
- Action generation prompts

## Structured Output Generation

LLM output example:

```json
{
  "intent": "schedule_meeting",
  "title": "Project Presentation",
  "attendee": "Krishna",
  "date": "2026-06-17",
  "time": "11:00 AM"
}
```

---

## AI Agent Design

Implemented:

- Planning Layer
- Action Layer
- Scheduling Layer
- Execution Layer

---

## Tool Calling Architecture

The LLM determines which tool should execute:

```text
Schedule Event

Create Note

Get Calendar Events

Generate Suggestions

Analyze Schedule
```

---

## AI Reliability

Implemented safeguards:

- Schema Validation
- Error Handling
- Conflict Detection
- Time Parsing Validation
- Fallback Responses

---

# 🛠 Tech Stack

## AI Layer

- Google Gemini AI
- Prompt Engineering
- AI Agent Workflows
- Intent Recognition
- Structured Output Parsing

## Backend

- FastAPI
- Python
- SQLAlchemy
- Pydantic
- Uvicorn

## Frontend

- React
- Vite
- Axios
- React Hooks

## Database

- MySQL

## Integrations

- Google Calendar API
- Google OAuth 2.0

---

# 📂 Project Structure

```text
Yashraj-AI-Assistant-OS/
│
├── backend/
│   ├── api/
│   ├── services/
│   ├── models/
│   ├── scheduling/
│   └── integrations/
│
├── frontend/
│   ├── src/
│   ├── components/
│   ├── pages/
│   └── services/
│
├── docs/
│
├── screenshots/
│
└── tests/
```

---

# 📸 Screenshots

## Executive Dashboard

![Dashboard](docs/screenshots/dashboard-overview.png)

---

## Analytics Dashboard

![Analytics](docs/screenshots/dashboard-analytics.png)

---

## AI Assistant Scheduling

![AI Chat](docs/screenshots/ai-chat-scheduling.png)

---

## Calendar Management

![Calendar](docs/screenshots/calendar-management.png)

---

## Notes Management

![Notes](docs/screenshots/notes-management.png)

---

# ⚙ Installation

## Clone Repository

```bash
git clone https://github.com/YashrajThube/Yashraj-AI-Assistant-OS.git

cd Yashraj-AI-Assistant-OS
```

---

## Backend Setup

Create virtual environment:

```bash
python -m venv .venv
```

Activate:

Windows

```powershell
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## Frontend Setup

```bash
cd frontend

npm install

npm run dev
```

---

## Backend Run

```bash
uvicorn app.main:app --reload
```

---

# 🔑 Environment Variables

Create:

```env
DATABASE_URL=

GOOGLE_CLIENT_ID=

GOOGLE_CLIENT_SECRET=

GEMINI_API_KEY=
```

---

# 📅 Google Calendar Integration

Supported Features:

✅ OAuth Authentication

✅ Event Creation

✅ Event Updates

✅ Event Deletion

✅ Calendar Synchronization

✅ Conflict Detection

✅ Availability Checking

---

# 💡 Example Prompts

## Scheduling

```text
Schedule a project discussion tomorrow at 11 AM with Krishna
```

```text
Create a client meeting next Monday at 3 PM
```

```text
Book a team standup every weekday at 9 AM
```

---

## Notes

```text
Create a note about Gemini API integration
```

```text
Save project deployment checklist
```

---

## Analytics

```text
Show my upcoming meetings
```

```text
Analyze my schedule this week
```

---

# 📈 AI Capabilities

- Natural Language Understanding
- Intent Classification
- Entity Recognition
- Scheduling Intelligence
- Calendar Reasoning
- Productivity Recommendations
- Conversational AI
- Workflow Automation

---

# 🎓 Learning Outcomes

This project demonstrates expertise in:

- Generative AI
- Large Language Models (LLMs)
- AI Agents
- Prompt Engineering
- Workflow Automation
- Tool Calling
- FastAPI Development
- Google Calendar API
- Production AI Systems

---

# 🚀 Future Enhancements

- Multi-Agent Architecture
- Voice Assistant Integration
- Meeting Summarization
- Email Automation
- WhatsApp Integration
- RAG Knowledge Base
- Vector Database Support
- MCP Server Integration
- LangGraph Workflows
- Autonomous Planning Agents

---

# 👨‍💻 Author

## Yashraj Thube

Generative AI Engineer | AI Agent Developer | LLM Applications Builder

GitHub:

https://github.com/YashrajThube

LinkedIn:

https://www.linkedin.com/in/yashraj-thube

---

# ⭐ Why This Project Matters

This project demonstrates real-world implementation of:

- Generative AI Applications
- LLM-Powered Productivity Systems
- AI Agent Design
- Enterprise Workflow Automation
- Calendar Intelligence
- Natural Language Scheduling

It is designed as a portfolio-grade AI engineering project showcasing practical use of Large Language Models in business productivity environments.

---

# 📜 License

MIT License

---

### ⭐ Star this repository if you found it useful.
