FROM rasa/rasa:3.6.16

# Use Rasa's virtual environment path to avoid permission issues
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Copy your code
COPY . /app

# Install only your custom dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Start Rasa server with API access
ENTRYPOINT ["rasa", "run", "--enable-api", "--cors", "*", "--port", "8000"]