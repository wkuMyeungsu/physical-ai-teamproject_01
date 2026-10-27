Stage 1: Open the webpage (웹페이지 열기)

This is the page on the PC or laptop that everyone watches during the demo. It has two areas: the "원문 컨베이어" panel, which will show the live camera view of the conveyor (empty until a phone connects), and the dashboard panel, which will later show OCR results and the RAG search box.

What to build: a FastAPI app that serves one HTML page at /. At this stage it can just be a layout with placeholder panels. This is the easiest stage and a good first task to confirm your Docker setup works (docker compose up, open the browser, see the page).

Stage 2: QR pairing (QR 연동 · 세션 페어링)

The problem this solves: the server needs to know which phone belongs to which dashboard. If two teams (or two PCs) run the demo at once, their video streams must not get mixed up. A session is just a random ID that links one dashboard to one phone.

The flow is:

When the dashboard page loads, it asks the server to create a session. The server generates an ID like a8f3k2 and remembers it (in Redis or a Python dict at first).
The server returns a QR code that encodes a URL such as https://your-server/phone?session=a8f3k2. The qrcode Python library can generate this as an image.
The dashboard displays the QR code.
The phone scans it with its normal camera app, which opens that URL in the phone’s browser.
The phone page connects to the server with the session ID, and the server tells the dashboard “phone paired” so it can hide the QR code and show “connected.”

What to build: an endpoint that creates a session and returns a QR image, a /phone page for the phone, and a WebSocket for the dashboard so the server can push the “paired” message to it.

Stage 3: Real-time video (실시간 영상 · 휴대폰 → 서버)

Once paired, the phone becomes a wireless camera pointed at the conveyor.

The phone page uses the browser’s getUserMedia API to open the rear camera. Every 200–500 ms, it draws the current video frame onto a hidden <canvas>, converts it to a JPEG, and sends it to the server over a WebSocket tagged with the session ID.

The server does two things with each frame: it forwards it to the matching dashboard, so the conveyor panel shows a live view, and it pushes it into a Redis queue so the OCR worker can process it in stage 4.

What to build: the JavaScript on the /phone page (camera, canvas, WebSocket send), and a WebSocket endpoint on the server that receives frames and relays them.

The one thing to set up early

As mentioned before, the phone browser will only allow camera access over HTTPS. Test this as soon as stage 2 works, because it’s the most common reason stage 3 silently fails. The quickest route for development is a tunnel like ngrok or Cloudflare Tunnel, which gives you an HTTPS URL to put in the QR code without managing certificates.

If it helps, I can write a minimal working version of stages 1–3 (FastAPI server, dashboard page, and phone page) that you can run with Docker and build on