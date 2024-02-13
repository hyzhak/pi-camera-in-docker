#!/usr/bin/env bash

set -e

for pkg in docker.io docker-doc docker-compose podman-docker containerd runc; do sudo apt-get remove $pkg; done

curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh ./get-docker.sh

# verify
sudo docker run hello-world
