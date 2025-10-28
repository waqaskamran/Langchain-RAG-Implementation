FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire app
COPY . .

# Run Flask
CMD ["flask", "run", "--host=0.0.0.0", "--port=5002"]
