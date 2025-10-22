#!/bin/bash
# MusicDiff Credential Setup Script

echo "🎵 MusicDiff Credential Setup"
echo "=============================="
echo

# Create .env file
ENV_FILE=".env"

if [ -f "$ENV_FILE" ]; then
    echo "⚠️  .env file already exists. Backing up to .env.backup"
    cp .env .env.backup
fi

echo "# MusicDiff Environment Variables" > $ENV_FILE
echo "# Generated on $(date)" >> $ENV_FILE
echo "" >> $ENV_FILE

# Spotify Setup
echo "📗 SPOTIFY SETUP"
echo "----------------"
echo "1. Go to: https://developer.spotify.com/dashboard"
echo "2. Create an app"
echo "3. Set redirect URI (http://localhost:8888/callback OR https://localhost:8888/callback)"
echo "4. Get your Client ID and Client Secret"
echo

read -p "Enter Spotify Client ID: " SPOTIFY_CLIENT_ID
read -p "Enter Spotify Client Secret: " SPOTIFY_CLIENT_SECRET
read -p "Enter Spotify Redirect URI [https://localhost:8888/callback]: " SPOTIFY_REDIRECT_URI
SPOTIFY_REDIRECT_URI=${SPOTIFY_REDIRECT_URI:-https://localhost:8888/callback}

echo "export SPOTIFY_CLIENT_ID=\"$SPOTIFY_CLIENT_ID\"" >> $ENV_FILE
echo "export SPOTIFY_CLIENT_SECRET=\"$SPOTIFY_CLIENT_SECRET\"" >> $ENV_FILE
echo "export SPOTIFY_REDIRECT_URI=\"$SPOTIFY_REDIRECT_URI\"" >> $ENV_FILE
echo "" >> $ENV_FILE

echo "✓ Spotify credentials saved!"
echo

# Apple Music Setup
echo "📕 APPLE MUSIC SETUP (Optional - Skip if you only use Spotify)"
echo "----------------"
read -p "Do you want to set up Apple Music? (y/n): " setup_apple

if [ "$setup_apple" = "y" ] || [ "$setup_apple" = "Y" ]; then
    echo
    echo "Apple Music requires an Apple Developer account (\$99/year)"
    echo "Setup instructions:"
    echo "1. Go to: https://developer.apple.com/account"
    echo "2. Create a MusicKit Identifier"
    echo "3. Download the .p8 private key file"
    echo "4. Get your Team ID and Key ID"
    echo

    read -p "Enter Apple Team ID (10 chars, e.g., ABC123DEF4): " APPLE_TEAM_ID
    read -p "Enter Apple Key ID (10 chars, e.g., XYZ987WVU6): " APPLE_KEY_ID
    read -p "Enter path to .p8 file: " APPLE_KEY_PATH

    # Copy the key file to the config directory
    mkdir -p .musicdiff
    cp "$APPLE_KEY_PATH" .musicdiff/apple_music_key.p8

    echo "export APPLE_TEAM_ID=\"$APPLE_TEAM_ID\"" >> $ENV_FILE
    echo "export APPLE_KEY_ID=\"$APPLE_KEY_ID\"" >> $ENV_FILE
    echo "export APPLE_PRIVATE_KEY_PATH=\"$(pwd)/.musicdiff/apple_music_key.p8\"" >> $ENV_FILE
    echo "# export APPLE_USER_TOKEN=\"get_from_musickit_js\"  # TODO: Get user token" >> $ENV_FILE
    echo "" >> $ENV_FILE

    echo "✓ Apple Music credentials saved!"
    echo "⚠️  Note: You still need to get a user token via MusicKit JS"
else
    echo "# Apple Music - Not configured" >> $ENV_FILE
    echo "# export APPLE_TEAM_ID=\"\"" >> $ENV_FILE
    echo "# export APPLE_KEY_ID=\"\"" >> $ENV_FILE
    echo "# export APPLE_PRIVATE_KEY_PATH=\"\"" >> $ENV_FILE
    echo "# export APPLE_USER_TOKEN=\"\"" >> $ENV_FILE
    echo "" >> $ENV_FILE
fi

echo
echo "✅ Setup complete!"
echo
echo "To use these credentials, run:"
echo "  source .env"
echo
echo "Then test with:"
echo "  source venv/bin/activate"
echo "  musicdiff init"
echo
