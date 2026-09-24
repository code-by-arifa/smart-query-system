# Smart Query Routing & Email Automation System

## How to run

### Backend
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt fpdf2==2.8.8
# create a .env file with: SUPABASE_URL, SUPABASE_KEY, GEMINI_API_KEY,
# GOOGLE_CLIENT_ID, JWT_SECRET, GMAIL_TOKEN_JSON, GMAIL_POLL_ENABLED
uvicorn app.main:app --reload

Before deploying or creating a new Supabase project, run the SQL files in
`backend/database/` in order, including migration `002_align_queries_schema.sql`.
Keep `.env`, OAuth credentials, Gmail tokens, `venv/`, and `node_modules/` out of
source-control and release ZIP files.

### Dashboard
cd dashboard
npm install
npm run dev

## What this demonstrates
Query ingestion via Gmail, AI-based classification (Gemini), rule-based routing
to departments, staff dashboard with role-based access, AI-assisted reply
drafting, and automated email delivery.
