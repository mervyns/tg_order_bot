#!/bin/bash

# Pull latest image
docker pull gcr.io/${PROJECT_ID}/hd-tg-bot:latest

# Stop and remove old container
docker stop hd-tg-bot
docker rm hd-tg-bot

# Start new container
docker run -d \
    --name hd-tg-bot \
    --restart unless-stopped \
    gcr.io/${PROJECT_ID}/hd-tg-bot:latest

# Cleanup old images
docker system prune -f