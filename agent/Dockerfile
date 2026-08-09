FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Hugging Face Spaces expects the container to answer on this port.
EXPOSE 7860

CMD ["python", "connectivity_spike.py", "start"]
