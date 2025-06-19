FROM rasa/rasa:3.6.16

# Use Rasa's internal venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

COPY . /app

# ✅ Install requirements WITHOUT --user or --break-system-packages
RUN pip install --no-cache-dir -r requirements.txt

# Launch Rasa server
ENTRYPOINT ["rasa", "run", "--enable-api", "--cors", "*", "--port", "8000"]
