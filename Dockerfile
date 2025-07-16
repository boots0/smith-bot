# Dockerfile
# This file contains the instructions for building a portable container image
# that includes your bot and all its dependencies.

# 1. Start with an official Python base image.
FROM python:3.10-slim

# 2. Set the working directory inside the container.
WORKDIR /app

# 3. Copy the dependency list into the container.
COPY requirements.txt .

# 4. Install the Python libraries your bot needs.
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy the rest of your application's code into the container.
COPY . .

# 6. Expose the port that the bot's internal Flask server will run on.
# This must match the BOT_WEBHOOK_PORT in your .env file.
EXPOSE 8080

# 7. The command to run when the container starts. This is defined in the Procfile.
# The 'CMD' instruction is often handled by the Procfile in platforms like Railway.
