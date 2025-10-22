# MusicDiff Setup Guide

Quick guide to get MusicDiff running with your music libraries.

## Quick Start (Spotify Only)

### 1. Get Spotify Credentials

1. Go to https://developer.spotify.com/dashboard
2. Click **"Create app"**
3. Fill in:
   - App name: `MusicDiff`
   - Redirect URI: `https://localhost:8888/callback` (or `http://localhost:8888/callback`)
4. Click **"Save"** → **"Settings"**
5. Copy your **Client ID** and **Client Secret**

**Note:** You can use either `http://` or `https://` - just make sure it matches what you set in the dashboard!

### 2. Set Environment Variables

Create a `.env` file in this directory:

```bash
export SPOTIFY_CLIENT_ID="your_client_id_here"
export SPOTIFY_CLIENT_SECRET="your_client_secret_here"
export SPOTIFY_REDIRECT_URI="https://localhost:8888/callback"  # Must match dashboard
```

### 3. Run MusicDiff

```bash
# Load credentials
source .env

# Activate virtual environment
source venv/bin/activate

# Initialize (creates database)
musicdiff init

# Test by fetching your Spotify library
musicdiff fetch --spotify-only

# View what you have
musicdiff status
```

When you run commands that need authentication, a browser will open for you to authorize the app.

---

## Full Setup (Spotify + Apple Music)

### Apple Music Requirements

⚠️ **Requires Apple Developer Account ($99/year)**

### 1. Create MusicKit Identifier

1. Go to https://developer.apple.com/account/resources/identifiers/list/musicId
2. Click **"+"** to create new identifier
3. Select **"MusicKit Identifier"**
4. Enter description: `MusicDiff`
5. Click **"Continue"** → **"Register"**

### 2. Create Private Key

1. Go to https://developer.apple.com/account/resources/authkeys/list
2. Click **"+"** to create new key
3. Enter name: `MusicDiff Key`
4. Check **"MusicKit"**
5. Click **"Continue"** → **"Register"**
6. **Download** the `.p8` file (you can only download once!)
7. Note your **Key ID** (10 characters)

### 3. Get Team ID

1. Go to https://developer.apple.com/account
2. Look for **Team ID** in the membership section (10 characters)

### 4. Set All Environment Variables

Add to your `.env` file:

```bash
# Spotify
export SPOTIFY_CLIENT_ID="your_spotify_client_id"
export SPOTIFY_CLIENT_SECRET="your_spotify_client_secret"
export SPOTIFY_REDIRECT_URI="https://localhost:8888/callback"

# Apple Music
export APPLE_TEAM_ID="ABC123DEF4"
export APPLE_KEY_ID="XYZ987WVU6"
export APPLE_PRIVATE_KEY_PATH="~/Documents/MusicDiff/.musicdiff/apple_music_key.p8"
export APPLE_USER_TOKEN="eyJhbGc..."  # See below
```

### 5. Get Apple Music User Token

The user token is complex - you need to use MusicKit JS in a web browser.

**Simple method:**
1. Go to https://music.apple.com
2. Open browser dev tools (F12)
3. Go to Console tab
4. Paste this and press Enter:
```javascript
MusicKit.getInstance().musicUserToken
```
5. Copy the token (starts with `eyJ...`)
6. Add it to your `.env` file

**Note:** User tokens expire - you'll need to refresh them periodically.

---

## Automated Setup Script

We've included a script to help:

```bash
chmod +x setup_credentials.sh
./setup_credentials.sh
```

This will prompt you for all credentials and create the `.env` file.

---

## Testing Your Setup

```bash
# Load credentials
source .env

# Activate venv
source venv/bin/activate

# Initialize
musicdiff init

# Should show your credentials are found
musicdiff status

# Test Spotify
musicdiff fetch --spotify-only

# Test Apple Music (if configured)
musicdiff fetch --apple-only
```

---

## Common Issues

### "Spotify authentication failed"
- Check your Client ID and Secret are correct
- Make sure redirect URI is exactly `http://localhost:8888/callback`
- Try regenerating your Client Secret

### "Apple Music user token invalid"
- User tokens expire - get a new one
- Make sure you're logged into Apple Music in your browser

### "Permission denied" errors
- Make sure the `.p8` key file is readable
- Check the path in `APPLE_PRIVATE_KEY_PATH` is correct

---

## Security Notes

- **Never commit** your `.env` file to git (it's in `.gitignore`)
- Keep your credentials secure
- The `.p8` private key is especially sensitive
- User tokens expire and need to be refreshed

---

## Next Steps

Once setup is complete:

1. **Initial Sync**: `musicdiff sync` (interactive mode)
2. **Automatic Syncs**: `musicdiff daemon` (runs every 24 hours)
3. **View History**: `musicdiff log`
4. **Resolve Conflicts**: `musicdiff resolve`

See `README.md` for full command documentation.
