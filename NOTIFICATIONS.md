# Admission Radar phone notifications

Admission Radar uses OneSignal Web Push so a subscribed phone can receive a notification when the monitor detects a new 2027 WATCH -> OPEN transition.

## One-time setup

1. Create a free OneSignal account and create a **Web Push** app for Admission Radar.
2. Set the site URL to:
   https://khushvoid.github.io/Admission-Radar/
3. In OneSignal, copy the **App ID** and put it into `index.html` by replacing:
   `REPLACE_WITH_YOUR_ONESIGNAL_APP_ID`
4. In OneSignal **Settings -> Keys & IDs**, copy the REST API Key.
5. In GitHub, open **Settings -> Secrets and variables -> Actions** for this repository and create:
   - `ONESIGNAL_APP_ID` = the same App ID
   - `ONESIGNAL_API_KEY` = the REST API Key
6. Open Admission Radar on the phone in a normal browser and tap **Enable phone alerts**, then allow notifications.

## What happens after setup

The GitHub Actions monitor checks every 30 minutes. When a 2027 entry changes from WATCH to OPEN, it sends a push notification to subscribed devices.

The notification includes:
- the institution/exam name
- a short reason
- **Apply now** action
- **Open Admission Radar** action

The API key is used only inside GitHub Actions and is never placed in the website.

## Important

Web push support depends on the browser/OS. On Android, Chrome and other supported Chromium browsers can receive web push. iOS/iPadOS support depends on the browser's installed-web-app/PWA requirements; if iPhone notifications are the priority, add Admission Radar to the Home Screen and allow notifications when prompted.

Do not put the OneSignal REST API Key in `index.html` or any public repository file.
