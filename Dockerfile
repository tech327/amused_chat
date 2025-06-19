FROM rasa/rasa:3.6.16

# Use Rasa's internal venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

COPY . /app

# Switch to root user to install packages
USER root

# Install requirements with proper permissions
RUN pip install --no-cache-dir -r requirements.txt

# Switch back to rasa user for security
USER rasa

# Launch Rasa server
ENTRYPOINT ["rasa", "run", "--enable-api", "--cors", "*", "--port", "8000"]