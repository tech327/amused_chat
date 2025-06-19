import mysql.connector

try:
    conn = mysql.connector.connect(
        host="72.167.148.18",             # your MySQL server IP
        user="amuseapp_amuse",            # your DB user
        password="amuseapp_amuse",        # your DB password
        database="amuseapp_amuse",        # your DB name
        port=3306                         # default MySQL port
    )
    print("✅ Successfully connected to remote MySQL!")
    conn.close()

except mysql.connector.Error as err:
    print("❌ Connection failed:", err)















from flask import Flask, request, jsonify
import mysql.connector
import os
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables from .env
load_dotenv()

# Set OpenAI API key and client
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

# MySQL DB config from .env
db_config = {
    "host": os.getenv("DB_HOST"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME"),
    "port": 3306  # Ensure port is defined
}

# Connect to MySQL database
try:
    db = mysql.connector.connect(**db_config)
    cursor = db.cursor(dictionary=True)
    print("✅ Connected to MySQL database.")
except Exception as e:
    print("❌ Failed to connect to database:", e)
    exit()

app = Flask(__name__)

def get_sql_from_gpt(user_query):
    prompt = f"""
You are an AI that converts user questions into MySQL queries.
The table name is `events` with columns:
id, title, address, lat, long, date_time, about, category_id, rating, user_id, created_at, link, visible_date, recurring, end_date, weekdays, dates, all_time, selected_weeks.

Return only a valid MySQL SELECT query. DO NOT include markdown (like ```sql) or comments. Only return the SQL.
The date_time column is in string format like '20/06/2025,20 : 30'.
Use STR_TO_DATE(date_time, '%d/%m/%Y,%H : %i') for comparisons.

The column `category_id` is an integer. You must not compare it to strings like 'music'. Use the correct numeric ID.
If the user says a category like "music", assume its ID is 6 (or set mapping).

User query: "{user_query}"
"""
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    # Strip extra formatting
    sql = response.choices[0].message.content.strip().strip('`').strip('"').replace("```sql", "").replace("```", "")
    return sql    # API endpoint to receive query
@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json()
    user_query = data.get("query", "").strip()

    if not user_query:
        return jsonify({"error": "Missing query"}), 400

    # Lowercase for comparison
    query_lower = user_query.lower()

    # Greeting detection
    greetings = ["hi", "hello", "hey", "hola", "hii", "hiii", "greetings"]
    if query_lower in greetings:
        return jsonify({
            "message": "👋 Hello! I'm your event assistant. You can ask me things like 'Show me events in June' or 'Find concerts in Deutschland'."
        })

    exit_phrases = ["ok", "bye", "goodbye", "thank you", "thanks", "see you"]
    if query_lower in exit_phrases:
        return jsonify({
            "message": "👋 Thank you! Have a great day. Let me know if you need help with events later."
        })

    try:
        sql = get_sql_from_gpt(user_query)
        cursor.execute(sql)
        results = cursor.fetchall()

        if not results:
            return jsonify({
                "sql": sql,
                "results": [],
                "message": "❌ No matching event details found for your query. Please try another date, location, or category."
            })

        return jsonify({
            "sql": sql,
            "results": results
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Run Flask server
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)