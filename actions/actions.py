from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
import mysql.connector
import os
import re
from datetime import datetime
from dateparser import parse as parse_date
from dotenv import load_dotenv
from openai import OpenAI
from rasa_sdk.events import UserUtteranceReverted

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise EnvironmentError("OPENAI_API_KEY not set in environment variables.")

client = OpenAI(api_key=OPENAI_API_KEY)

# DB Connection
try:
    db_config = {
        "host": os.getenv("DB_HOST"),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "database": os.getenv("DB_NAME"),
        "port": 3306
    }
    db = mysql.connector.connect(**db_config)
    cursor = db.cursor(dictionary=True)
except mysql.connector.Error as e:
    raise ConnectionError(f"Database connection failed: {e}")

# --- DATE SQL PARSER ---
def extract_date_sql_from_query(user_query: str) -> str:
    user_query = user_query.lower()
    today = datetime.now()
    current_year = today.year
    base_sql = "SELECT * FROM events WHERE"

    # Handle range like: between 1 June and 10 June
    date_range = re.findall(r"(?:between|from)\s+(.*?)\s+(?:and|to)\s+(.*)", user_query)
    if date_range:
        start_str, end_str = date_range[0]
        start_date = parse_date(start_str + f" {current_year}")
        end_date = parse_date(end_str + f" {current_year}")
        if start_date and end_date:
            return (
                f"{base_sql} STR_TO_DATE(date_time, '%d/%m/%Y,%H:%i') "
                f"BETWEEN '{start_date.date()}' AND '{end_date.date()}' LIMIT 10"
            )

    # Handle single date like: 15 June
    single_date = re.search(r"\d{1,2}\s+\w+|\w+\s+\d{1,2}", user_query)
    if single_date:
        parsed_date = parse_date(single_date.group() + f" {current_year}")
        if parsed_date:
            return (
                f"{base_sql} DATE(STR_TO_DATE(date_time, '%d/%m/%Y,%H:%i')) = "
                f"'{parsed_date.date()}' LIMIT 10"
            )

    # Handle monthly queries
    if "this month" in user_query:
        return (
            f"{base_sql} MONTH(STR_TO_DATE(date_time, '%d/%m/%Y,%H:%i')) = {today.month} "
            f"AND YEAR(STR_TO_DATE(date_time, '%d/%m/%Y,%H:%i')) = {today.year} LIMIT 10"
        )

    if "next month" in user_query:
        next_month = (today.month % 12) + 1
        next_year = today.year + (1 if next_month == 1 else 0)
        return (
            f"{base_sql} MONTH(STR_TO_DATE(date_time, '%d/%m/%Y,%H:%i')) = {next_month} "
            f"AND YEAR(STR_TO_DATE(date_time, '%d/%m/%Y,%H:%i')) = {next_year} LIMIT 10"
        )

    # Handle specific month names
    month_map = {
        "january": 1,
        "february": 2,
        "march": 3,
        "april": 4,
        "may": 5,
        "june": 6,
        "july": 7,
        "august": 8,
        "september": 9,
        "october": 10,
        "november": 11,
        "december": 12
    }

    for month_name, month_num in month_map.items():
        if month_name in user_query:
            return (
                f"{base_sql} MONTH(STR_TO_DATE(date_time, '%d/%m/%Y,%H:%i')) = {month_num} "
                f"AND YEAR(STR_TO_DATE(date_time, '%d/%m/%Y,%H:%i')) = {today.year} LIMIT 10"
            )

    return ""  # default fallback if no match
# --- GPT SQL FALLBACK ---
def generate_sql_from_gpt(user_query: str) -> str:
    prompt = f"""
You are an AI that converts natural language into MySQL SELECT queries.
The table is `events` with columns: id, title, address, lat, long, date_time, about, category_id, rating, user_id, created_at, link, visible_date, recurring, end_date, weekdays, dates, all_time, selected_weeks.
Use STR_TO_DATE(date_time, '%d/%m/%Y,%H:%i') for date comparisons.
Category mapping:
• music → 6
• sports → 3
• art → 4
• education → 5
• tech → 2
• food → 7
Only return a SELECT statement with LIMIT 10.
User query: "{user_query}"
"""
    res = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    sql = res.choices[0].message.content.strip().replace("```sql", "").replace("```", "")
    return sql

# --- FORMAT EVENTS FOR DISPLAY ---
def format_events(events: List[Dict]) -> str:
    if not events:
        return "no matching events."

    formatted = []
    for i, event in enumerate(events, start=1):
        block = (
            f"📅 *Event {i}*\n"
            f"• *Title:* {event.get('title', 'N/A')}\n"
            f"• *Date & Time:* {event.get('date_time', 'N/A')}\n"
            f"• *Location:* {event.get('address', 'N/A')}\n"
            f"• *Link:* {event.get('link', 'N/A')}\n"
            f"• *Rating:* {event.get('rating', 'N/A')}/5\n"
            f"• *About:* {event.get('about', 'N/A')}\n"
        )
        formatted.append(block)

    return "\n\n".join(formatted)

# --- ACTION TO FETCH EVENTS ---
class ActionFetchEventData(Action):
    def name(self) -> Text:
        return "action_fetch_event_data"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        user_query = tracker.latest_message.get("text")

        try:
            sql = extract_date_sql_from_query(user_query)
            if not sql:
                sql = generate_sql_from_gpt(user_query)

            cursor.execute(sql)
            results = cursor.fetchall()
            output = format_events(results)

        except Exception as e:
            output = f"⚠️ Error: {str(e)}"

        dispatcher.utter_message(text=output)
        return []

# --- GENERAL EVENT FAQ HANDLER ---
class ActionGeneralInfo(Action):
    def name(self) -> Text:
        return "action_general_info"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        user_query = tracker.latest_message.get("text")

        prompt = f"""
You are an assistant that answers general questions about events.
Answer clearly in 3–4 lines only.

Question: "{user_query}"
"""

        try:
            res = client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5
            )
            response = res.choices[0].message.content.strip()
        except Exception as e:
            response = f"⚠️ Error fetching info: {str(e)}"

        dispatcher.utter_message(text=response)
        return []





class ActionFallback(Action):
    def name(self) -> Text:
        return "action_fallback"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: 'Tracker',
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        dispatcher.utter_message(text=(
            " I'm sorry, I didn't understand that. "
            "Could you rephrase it?\n\n"
            "Try something like:\n• Show events happening in June\n"
            "• Events between 5th and 10th July\n• Music shows next month 🎶"
        ))
        return [UserUtteranceReverted()]