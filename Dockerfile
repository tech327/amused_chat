FROM rasa/rasa:3.6.16

# Use Rasa's internal venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

COPY . /app

# Force reinstall to avoid conflicts with existing packages
RUN pip install --no-cache-dir --force-reinstall -r requirements.txt

# Launch Rasa server
ENTRYPOINT ["rasa", "run", "--enable-api", "--cors", "*", "--port", "8000"]