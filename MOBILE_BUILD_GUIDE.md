# Android APK Build & Network Connection Guide

## Your Network Configuration
- **Machine IP**: 172.16.4.60
- **Backend Port**: 8000
- **API Base URL**: http://172.16.4.60:8000

## Prerequisites Checklist
- [x] Machine IP: 172.16.4.60
- [x] Environment file created: `.env` with `EXPO_PUBLIC_API_BASE_URL=http://172.16.4.60:8000`
- [ ] Backend running on `0.0.0.0:8000` (NOT 127.0.0.1)
- [ ] Android Device or Emulator available
- [ ] Expo CLI installed globally

## Step 1: Start Backend (CRITICAL)
The backend MUST listen on all network interfaces (0.0.0.0):

```powershell
# Open a NEW terminal window and run:
cd C:\Users\ze9167523\IdeaProjects\doctel
py -3.12 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

✅ You should see: `Uvicorn running on http://0.0.0.0:8000`

## Step 2: Verify Network Connection
Test that your computer's backend is accessible from another device/emulator:

```powershell
Invoke-WebRequest -Uri "http://172.16.4.60:8000/healthz" -UseBasicParsing
```

Expected response: `StatusCode: 200`

## Step 3: Build APK

### Option A: Build for Internal Testing (Recommended for First Build)

```powershell
cd C:\Users\ze9167523\IdeaProjects\doctel\mobile

# Build APK
expo build:android --type apk
```

When prompted:
- Choose "Managed workflow"
- You'll be asked to create an Expo account if you don't have one
- Build will take 5-10 minutes
- You'll get a download link when complete

### Option B: Build for Production Release
```powershell
expo build:android --type app-bundle
```

## Step 4: Install APK on Android Device

### On Physical Device:
1. Download the APK to your computer from the Expo build link
2. Transfer APK to your Android phone
3. Go to Settings → Security → Unknown Sources (enable)
4. Open file manager and tap the APK to install

### On Android Emulator:
```powershell
# After downloading APK
adb install -r C:\path\to\downloaded.apk
```

## Step 5: Test App Connection

1. Open DocIntel app on Android device
2. Login with EC number or email
3. Click "Upload" tab to upload a document
4. Ask a question
5. If you get responses, the **network connection is working!**

## Troubleshooting

### "Unable to connect to backend"
- ✅ Is backend running on `0.0.0.0` (not 127.0.0.1)?
- ✅ Can you reach it from this PC? `Invoke-WebRequest -Uri "http://172.16.4.60:8000/healthz"`
- ✅ Is Android device on same WiFi as your PC?
- ✅ No firewall blocking port 8000?

### "Connection refused"
- Check backend console for errors
- Make sure Ollama is running: `ollama serve` in another terminal
- Check database connectivity

### APK shows "localhost"
- `.env` file may not be loaded properly
- Delete `mobile/.env` and rebuild
- Or check that `EXPO_PUBLIC_API_BASE_URL` is correctly set

## Key Files Modified
- `mobile/.env` - Network API configuration

## Network Testing Commands
```powershell
# Test from Windows
Invoke-WebRequest -Uri "http://172.16.4.60:8000/healthz"

# Test from Android device (via adb)
adb shell "curl http://172.16.4.60:8000/healthz"

# Show network info
ipconfig /all
```

---

**Next Steps:**
1. Wait for Expo CLI installation to complete
2. Ensure backend is running on 0.0.0.0
3. Run APK build command
4. Test on device
