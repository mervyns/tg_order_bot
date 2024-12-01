# Use Python 3.10 slim image
FROM python:3.10-slim-bullseye

# Set working directory
WORKDIR /app

# Install system dependencies if needed
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install poetry
RUN pip install poetry==1.6.1
RUN poetry config virtualenvs.create false

# Copy dependency files first
COPY pyproject.toml poetry.lock ./

# Install dependencies
RUN poetry install --no-root --only main

# Copy the rest of the application
COPY . .

# Set environment variables for production
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Run the bot
CMD ["poetry", "run", "forwarder"]