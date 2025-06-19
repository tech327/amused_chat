from flask import Flask, request, jsonify
import mysql.connector
import os
import re
from dotenv import load_dotenv
from openai import OpenAI
from datetime import datetime

# Load environment variables
load_dotenv()

# OpenAI client setup
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

# MySQL configuration
db_config = {
    "host": os.getenv("DB_HOST"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME"),
    "port": 3306
}

# Connect to MySQL
try:
    db = mysql.connector.connect(**db_config)
    cursor = db.cursor(dictionary=True)
    print("✅ Connected to MySQL database.")
except Exception as e:
    print("❌ Failed to connect to database:", e)
    exit()

app = Flask(__name__)

# --- Utilities ---

def fix_sql_year(sql):
    """Replaces hardcoded 2022 with the current year in SQL query."""
    current_year = str(datetime.now().year)
    return sql.replace("2022", current_year)

def is_info_query(query):
    """Detects if the query is informational (non-SQL)."""
    query_lower = query.lower()

    # Prevent from treating date-based searches as info queries
    if any(keyword in query_lower for keyword in [
        " on ", " at ", " in ", "near", "around", "next", "today", "tomorrow", "weekend",
        "january", "february", "march", "april", "may", "june", "july", "august", "september",
        "october", "november", "december", "2025", "2024"
    ]):
        return False

    info_patterns = [
        r"\bwhat\s+(happens|is|are|do|does|happening)\b.*\b(event|events|festival|function)?",
        r"\btell\s+me\s+about\b",
        r"\bhow\s+(do|can|to)\b.*\b(add|organize|create)\b.*\b(event|events)?",
        r"\bfields.*event\b",
        r"\bparameters.*event\b",
        r"\bdescribe\b.*\b(event|festival)",
        r"\b(event|festival)\s+details\b",
        r"\bwhat\s+is\s+[a-z\s]+\b"
    ]

    return any(re.search(p, query_lower) for p in info_patterns)

def get_sql_from_gpt(user_query):
    prompt = f"""
You are an AI that converts natural language questions into MySQL SELECT queries.

The database has a table named `events` with these columns:
id, title, address, lat, long, date_time, about, category_id, rating, user_id, created_at, link, visible_date, recurring, end_date, weekdays, dates, all_time, selected_weeks.

Rules:
- `date_time` is a string like '20/06/2025,20 : 30'
- Use STR_TO_DATE(date_time, '%d/%m/%Y,%H : %i') for comparisons
- Use:
    STR_TO_DATE(date_time, '%d/%m/%Y,%H : %i') >= ...
    AND STR_TO_DATE(date_time, '%d/%m/%Y,%H : %i') < ...
- `category_id` mappings:
    • music → 6
    • sports → 3
    • art → 4
    • education → 5
    • tech → 2
    • food → 7

Return only a valid SELECT query. No markdown, no comments.
Always use LIMIT 10.

User query: "{user_query}"
"""
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    sql = response.choices[0].message.content.strip().strip('`').replace("```sql", "").replace("```", "")
    return sql

def format_results_with_gpt(results):
    prompt = f"""
You are an AI assistant that formats a list of event data into a friendly summary.
Include:
- Title 🎭
- Date & Time 📅
- Location 📍
- Link 🌐 (if available)
- Rating ⭐
- About ℹ️ (max 300 chars)

Use line breaks, no JSON or markdown.

Data:
{results}
"""
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5
    )
    return response.choices[0].message.content.strip()

def generate_info_answer(query):
    prompt = f"""
You are an AI expert on event descriptions.

Answer the following user question with informative and friendly detail (max 300 words).

User question: "{query}"
"""
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    return response.choices[0].message.content.strip()

# --- Main Endpoint ---

@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json()
    user_query = data.get("query", "").strip()

    if not user_query:
        return jsonify({"error": "Missing query"}), 400

    query_lower = user_query.lower()
    greetings = ["hi", "hello", "hey", "hola", "hii", "hiii", "greetings"]
    exits = ["ok", "bye", "goodbye", "thank you", "thanks", "see you"]

    if query_lower in greetings:
        return jsonify({
            "message": "👋 Hello! I'm your event assistant. Ask things like 'Events in June', 'Concerts in Delhi', or 'What happens in Holi events?'"
        })

    if query_lower in exits:
        return jsonify({
            "message": "👋 Thank you! Have a great day. I'm here if you need help with events later!"
        })

    # Handle informational queries (e.g. “What happens in music events?”)
    if is_info_query(user_query):
        answer = generate_info_answer(user_query)
        return jsonify({
            "message": "ℹ️ Informational answer:",
            "formatted": answer
        })

    # Handle SQL-based queries
    try:
        sql = get_sql_from_gpt(user_query)

        if not sql.lower().startswith("select"):
            return jsonify({
                "message": "❓ Sorry, I couldn't understand your request. Try asking about events by date, location, or category."
            })

        sql = fix_sql_year(sql)
        cursor.execute(sql)
        results = cursor.fetchall()

        if not results:
            return jsonify({
                "sql": sql,
                "results": [],
                "message": "❌ No matching event details found. Try different keywords, dates, or categories."
            })

        formatted_output = format_results_with_gpt(results)

        return jsonify({
            "sql": sql,
            "results": results,
            "formatted": formatted_output
        })

    except Exception as e:
        return jsonify({
            "error": str(e),
            "message": "⚠️ Something went wrong. Try again or ask in a different way."
        }), 500

# --- Start server ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)