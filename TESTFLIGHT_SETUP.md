# TradeSim - TestFlight Distribution Setup Guide

## 🚀 Complete TestFlight Distribution Checklist

This guide will walk you through preparing TradeSim for TestFlight distribution.

---

## 📋 Pre-Distribution Checklist

### ✅ 1. Apple Developer Account
- [ ] Active Apple Developer Program membership ($99/year)
- [ ] Signed in to Xcode with Apple ID (Xcode → Settings → Accounts)
- [ ] Team selected in project settings

### ✅ 2. App Store Connect Setup
- [ ] App created in App Store Connect (https://appstoreconnect.apple.com)
- [ ] Bundle ID registered (e.g., `com.yourcompany.TradeSim`)
- [ ] App name "TradeSim" reserved

### ✅ 3. Code Signing
- [ ] Development certificate installed
- [ ] Distribution certificate installed
- [ ] Provisioning profiles configured (Xcode can auto-manage)

### ✅ 4. App Assets
- [ ] App icon (1024×1024) added to Assets.xcassets
- [ ] All icon sizes generated (use `./generate_icons.sh`)
- [ ] Loading screen tested and working

### ✅ 5. App Information
- [ ] Version number set (e.g., 1.0.0)
- [ ] Build number set (must increment for each upload)
- [ ] Display name configured
- [ ] Bundle identifier unique and registered

---

## 🔧 Step 1: Configure Xcode Project Settings

### Update Bundle Identifier
1. Open your project in Xcode
2. Select the project in the Navigator (top-level)
3. Select the TradeSim target
4. Go to "Signing & Capabilities" tab
5. Update Bundle Identifier to match App Store Connect
   - Example: `com.yourcompany.TradeSim`
   - Must be unique across App Store

### Enable Automatic Signing (Recommended)
1. In "Signing & Capabilities"
2. Check ✅ "Automatically manage signing"
3. Select your Team from dropdown
4. Xcode will create/download provisioning profiles

### Set Version and Build Numbers
1. In General tab
2. Set **Version**: `1.0.0` (or your version)
3. Set **Build**: `1` (increment for each upload)

---

## 📱 Step 2: Update Info.plist & Privacy Settings

Your app requests notification permissions. Add privacy descriptions:

### Required Privacy Keys

Add these to your Info.plist (or in target settings):

**Notification Usage Description:**
- Key: `NSUserNotificationsUsageDescription`
- Value: `TradeSim sends notifications about rotation recommendations to help you stay informed of market opportunities.`

### Optional (if you add features later)

If you add camera, location, etc., you'll need:
- `NSCameraUsageDescription`
- `NSLocationWhenInUseUsageDescription`
- etc.

---

## 🎨 Step 3: Finalize App Icon

### Quick Method (Use Generated Icon)
```bash
# 1. Generate master icon (if not done)
./setup_sim_testing.sh  # Creates AppIcon-1024.png

# 2. Generate all sizes
./generate_icons.sh

# 3. Import to Xcode
# - Open Assets.xcassets
# - Right-click → New App Icon
# - Drag generated icons to appropriate slots
# - Make sure App Store (1024×1024) slot is filled
```

### Professional Method
1. Create final 1024×1024 icon in design tool
2. Export as PNG (no transparency, no rounded corners)
3. Save as `AppIcon-1024.png`
4. Run `./generate_icons.sh`
5. Import to Assets.xcassets

### Verify Icons
- [ ] All icon slots filled in Assets.xcassets
- [ ] No warnings or yellow triangles
- [ ] App Store icon (1024×1024) present
- [ ] Test on device to verify icon appears

---

## 🔒 Step 4: Configure Capabilities

Review app capabilities in Xcode:

1. Select target → "Signing & Capabilities"
2. Verify these are correct:

**Currently Required:**
- ✅ Push Notifications (if using local notifications)

**Not Required (unless you add them):**
- Background Modes
- In-App Purchase
- Game Center
- etc.

---

## 🧪 Step 5: Test on Physical Device

**Critical:** Test on a real iPhone/iPad before submitting!

1. Connect your device via USB or WiFi
2. Select your device in scheme selector
3. Build and run (Cmd+R)
4. Test thoroughly:
   - [ ] Loading screen appears and animates
   - [ ] App icon looks good on home screen
   - [ ] All tabs work correctly
   - [ ] Portfolio updates properly
   - [ ] Rotation recommendations work
   - [ ] Settings changes persist
   - [ ] Notifications request permission
   - [ ] No crashes or major bugs

---

## 📦 Step 6: Create Archive for TestFlight

### Archive the App

1. **Select Generic iOS Device**
   - In scheme selector (top-left)
   - Choose "Any iOS Device (arm64)"
   - Do NOT select a simulator

2. **Create Archive**
   - Menu: Product → Archive
   - Wait for build to complete (may take 1-5 minutes)
   - Archive will appear in Organizer

3. **Verify Archive**
   - Window → Organizer (or it opens automatically)
   - Select "Archives" tab
   - Find your TradeSim archive
   - Check version and build number are correct

### Distribute Archive

4. **Start Distribution**
   - In Organizer, select your archive
   - Click "Distribute App" button

5. **Choose Distribution Method**
   - Select: **"TestFlight & App Store"**
   - Click "Next"

6. **Choose Destination**
   - Select: **"Upload"**
   - Click "Next"

7. **Distribution Options**
   - ✅ "Upload your app's symbols" (recommended)
   - ✅ "Manage Version and Build Number" (recommended)
   - Click "Next"

8. **Automatic Signing**
   - Select: **"Automatically manage signing"**
   - Click "Next"

9. **Review and Upload**
   - Review all information
   - Click "Upload"
   - Wait for upload to complete (may take 5-15 minutes)

---

## 🎯 Step 7: Configure in App Store Connect

### After Upload Completes

1. **Go to App Store Connect**
   - Visit: https://appstoreconnect.apple.com
   - Sign in with your Apple ID

2. **Select Your App**
   - Click "My Apps"
   - Select "TradeSim"

3. **Go to TestFlight Tab**
   - Top navigation
   - Click "TestFlight"

4. **Wait for Processing**
   - Your build will say "Processing"
   - Usually takes 5-30 minutes
   - You'll get email when ready

5. **Add Test Information**
   - Click on your build when ready
   - Fill in "Test Information":
     - **What to Test**: Describe new features
     - **Privacy Policy URL**: (if you have one)
     - **Export Compliance**: Answer questions

### Export Compliance

For TradeSim (no encryption beyond HTTPS):
- **Does your app use encryption?** → YES
- **Does your app qualify for exemption?** → YES  
- **Uses standard encryption?** → YES
- No additional documentation needed

---

## 👥 Step 8: Add Testers

### Internal Testing (Apple Developer Team)

1. **TestFlight → Internal Testing**
2. Click "Internal Testing" group (or create new)
3. Add builds to test
4. Add internal testers (must be in your team)
5. Testers get email invitation

### External Testing (Anyone)

1. **TestFlight → External Testing**
2. Create new group (e.g., "Beta Testers")
3. Add builds to test
4. Add testers by email
5. Submit for Beta App Review (required first time)
6. Wait for approval (~24-48 hours)
7. Testers get invitation when approved

### Public Link Testing (Easiest)

1. **TestFlight → External Testing**
2. Create group
3. Enable "Public Link"
4. Share link with anyone
5. First requires Beta App Review approval

---

## 📝 Step 9: Beta App Review Information

Required for external testing:

### Test Details
- **App Name**: TradeSim
- **Description**: A cryptocurrency trading simulator for practicing investment strategies with live market data
- **What to Test**: Loading screen, portfolio tracking, rotation strategy, market data updates
- **Privacy Policy**: (URL if you have one)

### Contact Information
- **Email**: Your email
- **Phone**: Your phone number

### Demo Account (if needed)
- Not needed for TradeSim (no login required)

### Review Notes
```
TradeSim is an educational cryptocurrency trading simulator. It:
- Uses live market data from Coinbase public API
- Executes NO real trades
- Requires NO account or authentication
- Is for learning and practice only
- Requests notification permission to alert users about simulation events

No special instructions needed for testing.
```

---

## 🚀 Step 10: Submit for Beta Review

1. Fill in all required fields
2. Click "Submit for Review"
3. Wait for Apple approval (~24-48 hours)
4. Check email for status updates

---

## 📲 Step 11: Distribute to Testers

### After Approval

1. **Testers receive email invitation**
2. **Testers tap link in email**
3. **TestFlight app opens** (or directs to App Store to download it)
4. **Testers tap "Install"**
5. **App installs like normal app**

### Share Instructions with Testers

Send them this:

```
Thanks for testing TradeSim!

1. Check your email for TestFlight invitation
2. Tap "View in TestFlight" 
3. Install the TestFlight app if you don't have it
4. Tap "Install" to get TradeSim
5. Test the app and provide feedback

What to test:
- Loading screen on launch
- Portfolio tracking
- Market data updates
- Rotation recommendations
- Settings adjustments
- Overall usability

Please report any bugs or suggestions!
```

---

## 🔄 Step 12: Update Builds

### When You Need to Upload a New Version

1. **Increment Build Number**
   - In Xcode: General → Build
   - Change `1` to `2`, etc.
   - Build number MUST increase each upload

2. **Optional: Update Version**
   - For major changes: 1.0.0 → 1.1.0
   - For minor fixes: 1.0.0 → 1.0.1

3. **Commit Changes**
   ```bash
   git add .
   git commit -m "Bump version to 1.0.1 (build 2)"
   git tag v1.0.1
   ```

4. **Create New Archive**
   - Product → Archive
   - Distribute to TestFlight (same process)

5. **Update in App Store Connect**
   - New build appears after processing
   - Add to test groups
   - Testers get update notification

---

## 📊 Step 13: Collect Feedback

### Monitor TestFlight Metrics

In App Store Connect → TestFlight:
- **Installs**: How many testers installed
- **Sessions**: How often they use it
- **Crashes**: Any crash reports
- **Feedback**: Direct tester feedback

### Review Crash Reports

1. Xcode → Window → Organizer
2. Crashes tab
3. Select your app
4. Download crash logs
5. Fix critical issues

### Respond to Feedback

- Read tester feedback in App Store Connect
- Prioritize issues
- Make improvements
- Upload new builds

---

## 🎯 Common Issues & Solutions

### Issue: "No signing identity found"
**Solution**: 
- Xcode → Settings → Accounts
- Re-download profiles
- Enable "Automatically manage signing"

### Issue: "Bundle identifier already in use"
**Solution**:
- Change bundle ID in project settings
- Update in App Store Connect
- Must be globally unique

### Issue: "Missing compliance information"
**Solution**:
- App Store Connect → TestFlight → Build
- Answer export compliance questions
- For TradeSim: Uses standard encryption only

### Issue: "Missing app icon"
**Solution**:
- Run `./generate_icons.sh`
- Import to Assets.xcassets
- Ensure App Store (1024×1024) slot filled
- Archive again

### Issue: "Build processing forever"
**Solution**:
- Usually takes 5-30 minutes
- Check for email from Apple
- If > 1 hour, may need to re-upload

### Issue: "Beta review rejected"
**Solution**:
- Read rejection email carefully
- Address specific issues
- Common: Missing privacy policy, unclear purpose
- Resubmit when fixed

---

## 📋 Pre-Upload Checklist

Before each upload, verify:

- [ ] Version/build numbers incremented
- [ ] All icons present in Assets.xcassets
- [ ] Privacy descriptions in Info.plist
- [ ] Tested on physical device
- [ ] No critical bugs
- [ ] Loading screen works
- [ ] All tabs functional
- [ ] Settings persist
- [ ] Notifications work
- [ ] Certificate and provisioning profiles valid
- [ ] Scheme set to "Any iOS Device"
- [ ] Release configuration (not Debug)

---

## 🎉 Success Criteria

You'll know it worked when:

✅ Archive uploaded successfully
✅ Build appears in App Store Connect
✅ Processing completes (no errors)
✅ Beta review approved (for external testing)
✅ Testers receive invitation
✅ Testers can install and run app
✅ No critical crashes reported
✅ Positive feedback from testers

---

## 📚 Additional Resources

- **App Store Connect**: https://appstoreconnect.apple.com
- **TestFlight Help**: https://developer.apple.com/testflight/
- **App Review Guidelines**: https://developer.apple.com/app-store/review/guidelines/
- **Human Interface Guidelines**: https://developer.apple.com/design/human-interface-guidelines/

---

## 🚀 Quick Command Reference

```bash
# Make scripts executable
./make_executable.sh

# Generate app icon
./generate_icons.sh

# Test on simulator
./quick_test.sh

# View all visual assets
# Open VisualTestSuite.swift in Xcode

# Clean build
# Xcode: Cmd+Shift+K

# Archive
# Xcode: Product → Archive (with "Any iOS Device" selected)
```

---

**Ready to submit to TestFlight!** 🚀

Follow the steps above, and you'll have TradeSim available for beta testing in no time.

For questions, refer to Apple's TestFlight documentation or the App Store Connect help center.
