# TradeSim - Simulator Testing Checklist

## 🚀 Quick Start (30 seconds)

1. **Open Xcode**
   ```bash
   # If you have .xcworkspace (CocoaPods/SPM)
   open *.xcworkspace
   
   # Or if you have .xcodeproj
   open *.xcodeproj
   ```

2. **Select Simulator**
   - Click the scheme selector (top-left, near "TradeSim")
   - Choose: **iPhone 15 Pro** (recommended)

3. **Run the App**
   - Press `Cmd + R` or click the Play button
   - Wait for build to complete

4. **Watch for Loading Screen**
   - Should see animated loading screen for 1.5 seconds
   - Then transition to main app

---

## ✅ Complete Testing Checklist

### Loading Screen Tests

- [ ] **Loading screen appears on launch**
  - Dark gradient background visible
  - "TradeSim" title visible

- [ ] **Icon animation works**
  - Blue/cyan circle is visible
  - Chart symbol rotates smoothly
  - Pulsing effect on background circle

- [ ] **Chart bars animation**
  - Bars animate up and down
  - Smooth wave pattern
  - Colored gradient (blue to cyan to green)

- [ ] **Loading text visible**
  - "Loading markets..." text shows
  - Progress indicator visible

- [ ] **Transition is smooth**
  - Fades out after ~1.5 seconds
  - Main app fades in nicely
  - No jarring cuts

### App Icon Preview Tests

- [ ] **Open AppIconPreview.swift in Xcode**
- [ ] **Use Canvas Preview (Cmd + Option + Enter)**
- [ ] **Check icon clarity at all sizes**
  - 180×180 (main app icon) - clear?
  - 87×87 (settings) - still recognizable?
  - 60×60 (notification) - symbol visible?
  - 40×40 (smallest) - not too blurry?

- [ ] **Home screen preview looks good**
  - Icon stands out among other apps
  - Colors are appealing
  - Professional appearance

### App Icon Generator Tests

- [ ] **Open AppIconGenerator.swift**
- [ ] **View in Canvas Preview**
- [ ] **Try exporting icon** (tap export button)
- [ ] **Icon renders correctly**
  - Gradient is smooth
  - Chart symbol is centered
  - White color is crisp

### Main App Flow Tests

After loading screen:

- [ ] **Tab bar appears**
  - All 5 tabs visible
  - Icons are correct
  - Labels are readable

- [ ] **Portfolio tab loads**
  - Total value card shows
  - Current holding card displays
  - No crashes

- [ ] **Navigation works**
  - Can switch between tabs
  - Each view loads properly
  - Back navigation works

- [ ] **Refresh functionality**
  - Pull to refresh works
  - Refresh button in toolbar works
  - Loading indicator shows

### Scene Phase Tests

Test app lifecycle:

- [ ] **Background → Foreground**
  1. Run app
  2. Press `Cmd + Shift + H` (go to home)
  3. Tap app icon again
  4. Model.refresh() should be called

- [ ] **App doesn't crash when backgrounded**

### Different Simulator Tests

Test on multiple devices:

#### iPhone 15 Pro (6.1")
```bash
xcrun simctl boot "iPhone 15 Pro"
```
- [ ] Loading screen looks good
- [ ] Icons are sized correctly
- [ ] Text is readable

#### iPhone SE (4.7" - small)
```bash
xcrun simctl boot "iPhone SE (3rd generation)"
```
- [ ] Loading screen not cut off
- [ ] Tab bar fits properly
- [ ] Small icon (60px) still clear

#### iPhone 15 Pro Max (6.7" - large)
```bash
xcrun simctl boot "iPhone 15 Pro Max"
```
- [ ] Loading screen scales well
- [ ] No awkward spacing
- [ ] Icon looks sharp

#### iPad Pro 12.9"
```bash
xcrun simctl boot "iPad Pro (12.9-inch) (6th generation)"
```
- [ ] App runs (if iPad supported)
- [ ] Loading screen adapts
- [ ] Icon appropriate for tablet

### Appearance Tests

#### Light Mode
- [ ] Run app in light mode (default)
- [ ] Loading screen looks good
- [ ] Icon has good contrast
- [ ] Main app is readable

#### Dark Mode
1. In Simulator: Features → Toggle Appearance
2. Or use Control Center in iOS
- [ ] Loading screen still visible
- [ ] Icon maintains visibility
- [ ] Gradient still appealing
- [ ] Main app adapts properly

### Performance Tests

- [ ] **Loading time is reasonable**
  - Not too fast (< 1 second feels rushed)
  - Not too slow (> 3 seconds feels laggy)
  - Currently 1.5s - adjust in TradeSimApp.swift if needed

- [ ] **Animations are smooth**
  - No stuttering on rotating icon
  - Bars animate fluidly
  - Transitions are seamless
  - Note: May be slower in Simulator than on device

- [ ] **Memory usage is reasonable**
  - Check Debug navigator (Cmd + 6)
  - Memory should be stable
  - No obvious leaks

### Home Screen Icon Test

After running app once:

1. Press `Cmd + Shift + H` to go to home screen
2. Find TradeSim icon among apps
3. Check:
   - [ ] Icon is visible and not blank
   - [ ] Icon looks professional
   - [ ] Icon is distinguishable from others
   - [ ] Rounded corners applied correctly (iOS does this)

---

## 🐛 Troubleshooting

### Loading Screen Doesn't Appear

**Problem**: App goes straight to main view

**Solutions**:
1. Check TradeSimApp.swift has `@State private var isLoading = true`
2. Verify ZStack contains `if isLoading { LoadingView() }`
3. Rebuild: Clean Build Folder (Cmd + Shift + K), then build

### Loading Screen Frozen

**Problem**: Stuck on loading screen forever

**Solutions**:
1. Check Console for errors (Cmd + Shift + Y)
2. Verify `.task` block is executing
3. Check for exceptions in NotificationManager or TradeSimModel
4. Try commenting out `model.start()` temporarily

### Icon Not Showing

**Problem**: App has default Xcode icon

**Solutions**:
1. Icons need to be in Assets.xcassets/AppIcon.appiconset
2. Generate icons first with generate_icons.sh
3. Or manually add 1024×1024 to asset catalog
4. Clean build and reinstall app in simulator

### Animations Choppy

**Problem**: Animations are laggy or stuttering

**Solutions**:
1. Normal in Simulator (uses CPU, not GPU)
2. Test on real device for true performance
3. Close other apps/simulators
4. Reduce animation complexity if needed
5. Check Activity Monitor - make sure Mac isn't overloaded

### Build Errors

**Problem**: Xcode won't build

**Solutions**:
1. Check all Swift files compile (look for red errors)
2. Make sure all files are added to target
3. Verify import statements (SwiftUI, etc.)
4. Clean build folder (Cmd + Shift + K)
5. Restart Xcode if needed

---

## 📱 Testing on Physical Device

For best results, test on a real iPhone:

1. **Connect iPhone via USB or WiFi**
2. **Select your device** in scheme selector
3. **Trust developer certificate** if prompted
4. **Build and run** (Cmd + R)

Physical device benefits:
- ✓ True animation performance
- ✓ Accurate icon rendering
- ✓ Real-world touch interactions
- ✓ Actual Metal rendering
- ✓ True app launch experience

---

## 🎨 Creating Final Icon Assets

Once you're happy with the design:

### Option A: Use the generator script

1. Create master icon:
   ```bash
   # Open AppIconGenerator.swift in Xcode
   # Use Preview to see the icon
   # Export or screenshot at 1024×1024
   ```

2. Save as AppIcon-1024.png

3. Run generation script:
   ```bash
   chmod +x generate_icons.sh
   ./generate_icons.sh
   ```

4. Import to Xcode:
   - Open Assets.xcassets
   - Drag generated icons to AppIcon slots

### Option B: Manual Xcode approach

1. Open Assets.xcassets in Xcode
2. Click AppIcon
3. Drag your 1024×1024 PNG to the App Store slot
4. Xcode can auto-generate other sizes (right-click → Generate All Sizes)

### Option C: Use online tool

1. Export 1024×1024 icon from AppIconGenerator.swift
2. Upload to: https://appicon.co or similar
3. Download generated icon set
4. Import to Xcode

---

## ✨ Next Steps After Testing

- [ ] Test all checklist items above
- [ ] Take notes on any issues
- [ ] Adjust animations if needed
- [ ] Create final icon assets
- [ ] Add icons to asset catalog
- [ ] Test on physical device
- [ ] Get feedback from others
- [ ] Polish any rough edges

---

## 📊 Expected Results

✅ **Good Test Results Look Like:**

- Loading screen appears immediately
- Animations run smoothly (even if slightly choppy in Simulator)
- Icon is visible and professional
- Transition to main app is smooth
- All tabs work correctly
- No crashes or console errors
- App feels polished and complete

---

**Last Updated**: Generated with setup script
**Platform**: iOS Simulator
**Minimum iOS**: 17.0 (or your deployment target)

Happy Testing! 🚀
