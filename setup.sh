#!/bin/bash

echo "Writing permanent environment variables to /etc/environment ..."

sudo bash -c 'cat >> /etc/environment << EOF
API_ID="31040033"
API_HASH="87e3b8d52438304d90600c16afe70a23"
BOT_TOKEN="8283084188:AAFdJbGVqS3u02j5UsfCUtWGJgmEe25GhrM"
MONGO_URI mongodb+srv://sachindb:heysachin@cluster05.ukejys6.mongodb.net/?appName=Cluster05
ADMINS="8283084188,2133843296"
EOF'

echo "Adding environment variables to ~/.bashrc ..."

cat >> ~/.bashrc << 'EOF'
export API_ID="31040033"
export API_HASH="87e3b8d52438304d90600c16afe70a23"
export BOT_TOKEN="8283084188:AAFdJbGVqS3u02j5UsfCUtWGJgmEe25GhrM"
MONGO_URI mongodb+srv://sachindb:heysachin@cluster05.ukejys6.mongodb.net/?appName=Cluster05
export ADMINS="8283084188,2133843296"
EOF

echo "Reloading environment..."

# Load the new variables
source /etc/environment || true
source ~/.bashrc

echo "Permanent environment variables added and activated!"