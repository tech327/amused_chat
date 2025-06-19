from flask import Flask, request, jsonify
import mysql.connector
import os
from dotenv import load_dotenv
from openai import OpenAI
from datetime import datetime

# Loading  environment variables from the .env file
load_dotenv()

# Setting the  OpenAI API key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

# MySQL database configuration
db_config = {
    "host": os.getenv("DB_HOST"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME"),
    "port": 3306
}

# Connect to the SQL Database
try:
    db = mysql.connector.connect(**db_config)
    cursor = db.cursor(dictionary=True)
    print(" Connected to MySQL database.")
except Exception as e:
    print(" Failed to connect to database:", e)
    exit()

app = Flask(__name__)

# Fix hardcoded years in SQL (like 2022)
def fix_sql_year(sql):
    current_year = str(datetime.now().year)
    return sql.replace("2022", current_year)

# Converting user query intto SQL
def get_sql_from_gpt(user_query):
    prompt = f"""
You are an AI that converts natural language questions into MySQL SELECT queries.

The database has a table named `events` with the following columns:
id, title, address, lat, long, date_time, about, category_id, rating, user_id, created_at, link, visible_date, recurring, end_date, weekdays, dates, all_time, selected_weeks.

Formatting rules:
- `date_time` is a string like '20/06/2025,20 : 30'
- Use STR_TO_DATE(date_time, '%d/%m/%Y,%H : %i') for comparisons
- Use:
    STR_TO_DATE(date_time, '%d/%m/%Y,%H : %i') >= ...
    AND STR_TO_DATE(date_time, '%d/%m/%Y,%H : %i') < ...
- Category mappings (category_id):
    • music → 6
    • sports → 3
    • art → 4
    • education → 5
    • tech → 2
    • food → 7

Return only a valid SELECT query.
No markdown, no comments.
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

# Format SQL result to user-friendly text
def format_results_with_gpt(results):
    prompt = f"""
You are an AI assistant that formats a list of event data into a user-friendly summary.
Include:
- Title 
- Date & Time 
- Location 
- Link  (if available)
- Rating 
- About  (max 300 chars)

Use line breaks, no JSON, no markdown.

Data:
{results}
"""
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5
    )
    return response.choices[0].message.content.strip()

#  /ask endpoint
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
            "message": " Hello! I'm your event assistant. Ask me things like 'Events in June', 'Concerts in Malta', or 'What's happening next weekend?'"
        })

    if query_lower in exits:
        return jsonify({
            "message": " Thank you! Have a great day. I'm here if you need help with events later!"
        })

    try:
        sql = get_sql_from_gpt(user_query)

        if not sql.lower().startswith("select"):
            return jsonify({
                "message": " Sorry, I couldn't understand your request. Try asking about events by date, location, or category."
            })

        sql = fix_sql_year(sql)

        cursor.execute(sql)
        results = cursor.fetchall()

        if not results:
            return jsonify({
                "sql": sql,
                "results": [],
                "message": " No matching event details found. Try using different keywords, dates, or categories."
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
            "message": " Something went wrong. Try again or ask in a different way."
        }), 500

#  Running the  server
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
