FROM rasa/rasa:3.6.16

# Use Rasa's internal venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

COPY . /app

# ✅ Install Python packages even if it needs to override system packages
RUN pip install --no-cache-dir --break-system-packages -r requirements.txt

# Launch Rasa API server
ENTRYPOINT ["rasa", "run", "--enable-api", "--cors", "*", "--port", "8000"]
