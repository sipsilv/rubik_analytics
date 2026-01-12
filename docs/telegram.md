# 📱 Telegram Integration & Security System

> **Version:** 2.0  
> **Status:** ✅ Active  
> **Last Updated:** Jan 2026

![Telegram Integration Banner](https://img.shields.io/badge/Telegram-2FA%20%26%20Notifications-blue?style=for-the-badge&logo=telegram)

<div align="center">

| Feature | Status | Description |
| :--- | :---: | :--- |
| **Secure Login (2FA)** | ✅ | OTP verification via Telegram |
| **Instant Alerts** | ✅ | Real-time security notifications |
| **Admin Chat** | ✅ | Direct messaging Admin <-> User |
| **User Linking** | ✅ | Deep linking & verification |

</div>

---

## 📚 Table of Contents
- [1. Setup & Configuration](#1-setup--configuration)
- [2. User Linking Process](#2-user-linking-process)
- [3. Two-Factor Authentication (2FA)](#3-two-factor-authentication-2fa)
- [4. Admin Messaging System](#4-admin-messaging-system)
- [5. Troubleshooting & Debugging](#5-troubleshooting--debugging)

---

## 1. Setup & Configuration

### 🛠️ Prerequisites
- A Telegram Bot created via [@BotFather](https://t.me/BotFather).
- Bot Token added to your environment variables.

### ⚙️ Environment Variables
Add these to your `.env` file structure:

```env
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
# Optional: Only needed for production webhooks
TELEGRAM_WEBHOOK_URL=https://your-domain.com/api/v1/telegram/webhook
```

### 🗄️ Database Schema
The integration extends the core authentication schema:

| Table | Extension | Type | Description |
| :--- | :--- | :--- | :--- |
| **`users`** | `telegram_chat_id` | String | Unique Telegram Chat ID |
| **`users`** | `two_factor_enabled` | Boolean | Master toggle for 2FA |
| **`telegram_messages`** | *New Table* | Table | Stores full chat history |

---

## 2. User Linking Process

Every user must link their specific Telegram account to their Rubik Analytics profile.

### 🔗 Method A: Deep Link (Recommended)
The most seamless experience for users.

1.  User navigates to **Settings** → **Telegram Integration**.
2.  Clicks **Connect Telegram**.
3.  System generates a secure, one-time deep link.
4.  User clicks link → Opens Telegram → Clicks **Start**.
5.  ✅ Account Linked Instantly.

### 🤖 Method B: Manual Command
For users who prefer manual interaction.

1.  Open [@Rubik_Analytics_Bot](https://t.me/Rubik_Analytics_Bot).
2.  Send command:
    ```bash
    /start <REGISTERED_MOBILE_NUMBER>
    ```
3.  Example: `/start 9876543210`
4.  Bot verifies number against DB -> Links Account.

---

## 3. Two-Factor Authentication (2FA)

### 🛡️ Security Logic Flow

```mermaid
graph TD
    A[User Log In] --> B{Password Valid?}
    B -- No --> C[Error: Invalid Creds]
    B -- Yes --> D{Telegram Linked\nAND\n2FA Enabled?}
    D -- No --> E[Generate Token\n(Login Success)]
    D -- Yes --> F{OTP Provided?}
    F -- No --> G[Generate OTP]
    G --> H[Send to Telegram]
    H --> I[Return 401\n"OTP Required"]
    F -- Yes --> J{Verify OTP}
    J -- Valid --> E
    J -- Invalid --> K[Error: Invalid OTP]
```

### ⚙️ Configuration
> [!IMPORTANT]
> **Default State:** 2FA is **Disabled** (`False`) by default for new links to prevent lockouts. Users MUST manually opt-in.

1.  Go to **Settings** card.
2.  Toggle **"Two-Factor Authentication"**.
3.  **Result:** Next login will strictly enforce OTP.

### 🚨 Super User Rules
> [!WARNING]
> Even **Super Admins** are subject to 2FA if they enable it.

- **Status Bypass:** Super Admins CAN login even if `is_active=False`.
- **Security Check:** Super Admins **CANNOT** bypass 2FA if enabled.

---

## 4. Admin Messaging System

A direct line of communication between Administrators and Users.

### 📤 Sending (Admin → User)
- **Interface:** Admin Panel → Users → Click Message Icon.
- **Delivery:** User receives instant Telegram notification.
- **Format:**
  > 📩 **Message from Admin (sandeep)**
  >
  > Your subscription has been upgraded.
  >
  > — *Rubik Analytics Support*

### 📥 Receiving (User → Admin)
- **Interface:** User replies to the bot.
- **Delivery:** System forwards message to **All Admins** via Telegram + Logs to DB.
- **Format:**
  > 📨 **New Message from User (john_doe)**
  >
  > Thanks for the help!
  >
  > — *Reply via Admin Panel*

---

## 5. Troubleshooting & Debugging

### ❌ Common Issues

#### 1. "Login Loop" / Keeps asking for OTP
> **Symptom:** You enter password, get OTP, enter password again, get *new* OTP.
>
> **Fix:** The frontend Login page wasn't showing the OTP field. This is now **Fixed**. Ensure you see the "2-Step Verification" box.

#### 2. "TimeoutError" / 500 Error
> **Symptom:** Login fails with 500 error after 10-30 seconds.
>
> **Fix:** Server cannot reach Telegram API.
> - Check Internet Connection.
> - We increased timeout from 10s to **30s** to help with slow networks.

#### 3. Super User Skipping 2FA
> **Symptom:** You enabled 2FA but it logs you in directly.
>
> **Fix:** **Resolved.** The 2FA check is now placed *before* the Super User bypass logic.

### 🩺 Debugging Commands

**Check User Status:**
```bash
python backend/scripts/check_user.py <username>
```

**Verify DB State:**
```sql
SELECT username, telegram_chat_id, two_factor_enabled FROM users;
```

---
*Documentation maintained by Rubik Analytics Engineering Team.*
