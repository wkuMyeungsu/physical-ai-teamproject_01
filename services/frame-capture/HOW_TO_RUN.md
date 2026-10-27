# How to Start and Stop the Demo

The demo has three parts:

- **Docker Desktop** runs the app and Redis inside containers.
- **cloudflared** gives your Mac a public `https://` address so the phone can use its camera.
- **The app** is the FastAPI server, the dashboard page and the phone page.

You need **two terminals** open at the same time (in VS Code: **Terminal → New Terminal**, then the **+** button for a second one).

---

## Starting

### 1. Open Docker Desktop
Open the Docker app and wait until it says it's running (the whale icon in the menu bar stops animating).

### 2. Terminal 1: start the tunnel
```
cloudflared tunnel --url http://localhost:8000
```
Find the line that looks like this and **copy the address**:
```
|  https://some-random-words.trycloudflare.com  |
```
Leave this terminal open. Closing it stops the tunnel.

### 3. Terminal 2: start the app
```
cd "/Users/daeheekim/Desktop/청년 피지컬AI 일경험 프로젝트/Team_Project"
PUBLIC_BASE_URL=https://some-random-words.trycloudflare.com docker compose up --build
```
Replace the address with the one you copied in step 2. Wait until you see:
```
Uvicorn running on http://0.0.0.0:8000
```

### 4. Open the dashboard on your PC
Open the **`https://…trycloudflare.com`** address in your browser (not `localhost`).
You should see the 원문 컨베이어 panel with a QR code.

### 5. Connect the phone
1. Scan the QR code with the phone's **camera app**.
2. Open the link in **Safari** (iPhone) or **Chrome** (Android), not inside KakaoTalk or Naver.
3. Tap **카메라 시작** and choose **Allow** for camera access.
4. The dashboard changes to **휴대폰 연결됨** and shows the live video.

---

## Stopping

### 1. Terminal 2: stop the app
Press **Ctrl + C**, then run:
```
docker compose down
```

### 2. Terminal 1: stop the tunnel
Press **Ctrl + C**.

### 3. (Optional) Quit Docker Desktop
Click the whale icon in the menu bar, then **Quit Docker Desktop**.

---

## Good to know

- **The tunnel address changes every time** you restart cloudflared. Each time, start the app with the new address (step 3).
- **After editing code** in `app/`, stop the app (Ctrl + C) and run the step 3 command again so it rebuilds.
- **Video is choppy?** Choose **500 ms** in the interval menu on the phone page.

## Troubleshooting

| Problem | Fix |
|---|---|
| `failed to connect to the docker API` | Docker Desktop isn't running. Open it and wait. |
| Phone says HTTPS is missing | The app was started without `PUBLIC_BASE_URL`. Stop it and redo step 3. |
| `카메라 접근 실패 … denied permission` | Open the link in Safari/Chrome and allow the camera: **iPhone** Settings → Apps → Safari → Camera → Allow. **Android** tap the icon left of the address bar → Permissions → Camera → Allow. |
| Dashboard shows "세션 만료" | The app was restarted, so the dashboard made a new session. Scan the new QR code with the phone. |
| Tunnel address doesn't open | Check that terminal 1 (cloudflared) is still running. |
