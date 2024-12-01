#!/bin/bash

# Install Docker
apt-get update
apt-get install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian \
  $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io

# Configure Docker to start on boot
systemctl enable docker
systemctl start docker

# Pull and run the bot container
docker pull gcr.io/${PROJECT_ID}/hd-tg-bot:latest
docker run -d \
    --name hd-tg-bot \
    --restart unless-stopped \
    gcr.io/${PROJECT_ID}/hd-tg-bot:latest