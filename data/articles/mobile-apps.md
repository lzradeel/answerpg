# Mobile apps

Wrenfield for iOS and Android lets you read, write and organize pages and tasks on your phone or tablet. Download it from the App Store or Google Play and sign in with the same account you use on the web.

## Requirements

- iPhone and iPad need iOS 17 or iPadOS 17 or later.
- Android phones and tablets need Android 10 or later.

The current version of both apps is 6.5.

## Offline storage

The mobile apps keep recently opened pages and downloaded pages available offline. The default offline storage limit on mobile is 500 MB. You can change it in Settings > Storage to any value from 250 MB to 2 GB. When the limit is reached, the pages you opened least recently are removed first.

## Quick capture widget

Add the Wrenfield widget to your home screen to start a new page or task with one tap. On iOS, you can also share links, text and images from other apps into Wrenfield with the share sheet. Shared items go to your Inbox page unless you pick a space.

## Notifications

Push notifications cover mentions, task assignments, comments on pages you follow and tasks that are due today. Choose which ones you get in Settings > Notifications on the device. Notification settings on mobile are separate from email settings.

## App lock

To protect your workspace if someone else picks up your phone, turn on App lock in Settings > Privacy. The app then asks for Face ID, Touch ID or your Android fingerprint or PIN each time it opens. You can lock it immediately or after 1, 5 or 15 minutes in the background.

## Managed devices

Enterprise workspaces can manage the apps with Microsoft Intune, Jamf or any MDM that supports managed app configuration. Supported keys:

- `AllowedWorkspaceIDs` limits which workspaces can be signed in on the device.
- `DisableCopyPaste` blocks copying content out of the app.
- `RequireAppLock` forces App lock on and hides the setting.
