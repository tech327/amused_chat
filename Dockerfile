FROM rasa/rasa:3.6.16

# ✅ Use Rasa's virtual environment to avoid system-level conflicts
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

COPY . /app

# ✅ Install packages using --user to avoid permission denied errors
RUN pip install --no-cache-dir --user -r requirements.txt

# ✅ (Important) Ensure Python can find the user-installed packages
ENV PYTHONPATH="/root/.local/lib/python3.10/site-packages"

# Start the Rasa server
ENTRYPOINT ["rasa", "run", "--enable-api", "--cors", "*", "--port", "8000"]
