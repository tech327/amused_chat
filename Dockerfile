FROM rasa/rasa:3.6.16

WORKDIR /app

COPY . /app

# Install Python dependencies
COPY requirements.txt .  
RUN pip install --no-cache-dir -r requirements.txt

# Optional: If using shell scripts
RUN chmod +x start.sh || true

# Run Rasa server
ENTRYPOINT ["rasa", "run", "--enable-api", "--cors", "*", "--port", "8000"]