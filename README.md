# Walk-out detection demo

The MacBook webcam demo uses anonymous person tracks to flag a possible walk-out. The preview mirrors the camera. All zone coordinates refer to that mirrored view. Payment is simulated with the pay zone or the `p` key. A future Toast, Square, or Clover integration can supply a payment confirmation once a POS check has been associated with a visit.

## Run the two-camera demo in a browser

Double-click **Open Surveillance.command** in Finder. It opens the local dashboard in your browser. Keep the launcher window open while the dashboard is in use. If an older camera session is running, stop it first so it releases the devices.

1. Open **Camera setup**. Connect the iPhone through Continuity Camera, then click **Connect previews**. Use **Find cameras** if you need the available indexes. Check the camera names and flip any feed with **Mirror** as needed. Stop the previews before changing sources or mirroring.
2. Keep **Walk-out rules** enabled for the MacBook and disabled for the iPhone. Select the dining, payment, or exit tool, draw the shape in the MacBook preview, and click **Apply zone**.
3. Select **Shared landmarks**. Click the same fixed point in each feed, then repeat for at least four widely spaced points on the floor. Five or more points enable an extra accuracy check. **Freeze previews** holds the current images while you click.
4. Click **Save and start monitoring**. Use the live dashboard to view guests, review and delete alerts, mark dining guests paid for the demo, or stop the cameras.

Settings are saved to `walkout.multi.yaml`. Optional recordings are saved to `recordings/`. The iPhone shows the shared guest number, FPS, and date and time. The MacBook handles walk-out zones and evidence. Live camera processing uses the local Mac. The hosted Vercel demo uses simulated footage.

## Test the rules without a camera

From this repo, use the existing Python 3.12 virtual environment. For a fresh checkout, create one with `python3.12 -m venv .venv` and install with `.venv/bin/python -m pip install -r requirements.txt`.

```sh
.venv/bin/python -m survai.main --selftest
.venv/bin/python -m pytest -q
```

The self-test feeds generated person boxes into the detector. Expect one alert for the unpaid exit and zero for the paid exit.

## Try the MacBook preview

```sh
.venv/bin/python -m survai.main --list-cameras
.venv/bin/python -m survai.doctor --camera 0
.venv/bin/python -m survai.main --demo-mode --camera 0
```

Use the camera index that shows the built-in webcam. If macOS denies access, enable Camera for your terminal in **System Settings → Privacy & Security → Camera**, then restart the terminal.

1. Position the dot at the center of your tracking box inside **DINING** for at least three seconds. Wait for the `DINING` label.
2. Move steadily right until the dot reaches **EXIT**, then move out of frame. After the 1.5-second tracking grace period, the preview should flash **POSSIBLE WALK-OUT** and the terminal should log the alert.
3. Return, focus the preview, and press `r`. Dine again, then press `p` while still in **DINING**, or put the dot inside **PAY** for two seconds. Wait for the green `PAID` label, then repeat the exit. Expect zero alerts.
4. Press `q` to quit. The HUD shows the observed FPS.

The tracker confirms a new person over three consecutive detections and filters out nearly identical overlapping boxes. It uses position, motion, and recent clothing color samples to recover the same number and visit state when someone leans or is briefly covered. The default recovery window for covered people is five seconds from when they were last seen. Set `occlusion_seconds` in the YAML profile to adjust it. Similar clothing and longer overlaps can still cause tracking mistakes.

To record a take and play it back:

```sh
.venv/bin/python -m survai.main --demo-mode --camera 0 --record backup.mp4
.venv/bin/python -m survai.main --demo-mode --source backup.mp4
```

For the backup paid take, use the pay zone so the payment can be reproduced from the recording. The raw MP4 stores the camera frames. Replay applies the same mirror and tracking as the live preview.

## Calibrate the zones

Quit the demo preview, then run:

```sh
.venv/bin/python -m survai.main --calibrate --camera 0
```

- Press `1` for dining, `2` for payment, or `3` for the exit band. Click at least three corners around each area in order, then press Enter to apply it. Keep the exit band against the frame edge.
- For a fixed door camera, use `4` and click two exit-line endpoints. For a door on the right side of the image, click the top endpoint first. For a door on the left, click the bottom endpoint first.
- Right-click to undo a point. Press `s` to save and close, or `q` to leave without saving.

Calibration saves to `walkout.local.yaml` in the working directory, and demo mode picks it up automatically when run there. Use `--config path/to/config.yaml` in both modes to save and use a custom profile. To calibrate without a camera, use `--source backup.mp4` for a still from the start of the recording.

## Watch the live alert and evidence

```sh
.venv/bin/python -m survai.main --demo-mode --camera 0 --dashboard
```

Open the dashboard URL printed in the terminal. It defaults to [port 8765](http://127.0.0.1:8765) and picks a free port if that one is busy. Pass `--port 8766` to require a specific port.

An unpaid walk-out plays a system sound on macOS and adds a card with a cropped photo of the tracked guest. The app picks a sharp, unobstructed image from the recent frames before the exit and saves it as a JPEG. The clip link appears after the two-second post-roll and encode. The H.264 MP4 includes up to eight seconds before the alert and two seconds after it, bounded by available camera or replay footage. The JPEGs, clips, and `alerts.jsonl` are saved to `alerts/` by default. Use `--output` to choose another directory.

The count in the top right starts at **0 alerts** each time the app starts. Use **Delete** on a false alarm to remove it from the session's alert history and count. Its saved evidence and JSONL record remain on disk under the usual retention settings.

**Guests in view** shows tracks visible on the camera. A guest who briefly goes out of view keeps their visit state in memory during the recovery window. A paid guest stays in the panel until they exit, when their profile is removed. Photos are saved only for unpaid walk-out alerts.

## Hosted demo

Vercel builds the dashboard with `node scripts/build-dashboard.mjs`. Add a simulated guest, mark them paid, then send them out to remove the visit. A simulated unpaid exit creates a deletable alert with the earlier sample image. The hosted demo uses browser memory and synthetic images. Start the local Python app to use a real camera.

## MacBook and iPhone setup from the command line

Quit the single-camera preview, connect the iPhone by USB or use Continuity Camera wirelessly, and mount it in landscape with its back cameras facing the same room as the MacBook. Lock the iPhone and keep it nearby. From the repo directory, list the available indexes and start the two-camera demo:

```sh
.venv/bin/python -m survai.main --list-cameras
.venv/bin/python -m survai.main --calibrate-floor --config walkout.multi.yaml
.venv/bin/python -m survai.main --doctor-multi --config walkout.multi.yaml
.venv/bin/python -m survai.main --demo-mode --config walkout.multi.yaml --dashboard --grid
```

The sample assumes **MacBook 0** and **iPhone 1**. Edit `source` in `walkout.multi.yaml` or override the indexes with `--camera-a` and `--camera-b`. The iPhone flip is enabled in the sample. If the iPhone is missing, check Continuity Camera in iPhone **Settings → General → AirPlay & Continuity**. Grant your terminal Camera access in macOS **System Settings → Privacy & Security** if prompted. Open the dashboard URL printed by the app.

Both feeds stay live during calibration. Wait for the previews to brighten and sharpen, then click a physical landmark in the left view and the same landmark in the right view. Repeat for at least four widely spaced points and press **S**. Use five or more points for a leave-one-out error check. All points must be on the floor when `fusion.plane: floor`. If the MacBook view cuts off guests' feet, use `fusion.plane: head` and pick fixed landmarks at approximately head height. Head height varies as people sit or stand, so use floor mode where feet are visible. Keep both cameras fixed after calibration. Run `--check-calibration` to verify the grid and printed landmark errors. Use `--floor-grid` at startup or press **G** in the desktop preview to toggle the projected grid.

Draw dining, payment, and exit zones for the MacBook using:

```sh
.venv/bin/python -m survai.main --calibrate --config walkout.multi.yaml --camera cam1
```

The MacBook inherits your local single-camera layout until you save custom zones. Choose zones in the displayed orientation. The iPhone uses `walkout_enabled: false` and shows guest numbers, FPS, date, and time. It still helps match guest IDs. Shared floor calibration uses both feeds.

Guest IDs are shared across feeds. The app pairs frames by timestamp, projects each guest onto the shared plane, and uses a Kalman filter to follow their motion. Clothing color breaks close ties. A track gets a number after three sightings by default. Positions and clothing statistics stay in memory for the session and the app uses anonymous IDs. In this setup, only the MacBook updates dining, payment, and exit status. An unpaid exit can save one cropped photo and clip from the MacBook. The shared map shows guest positions, recent trails, and the projected camera outlines.

The MacBook and iPhone sample also enables `fusion.same_view_order`. When the configured anchor is clipped and floor matching misses a pair, this mode can pair clearly separated guests from left to right in synchronized frames with equal detection counts. Use it for cameras that face the same way and show guests in the same left-to-right order. Set it to `false` for camera angles that reverse that order.

To replay synchronized recordings from two angles or check the matching rules without cameras:

```sh
.venv/bin/python -m survai.main --demo-mode --config walkout.multi.yaml --sources front.mp4 side.mp4 --dashboard --grid
.venv/bin/python -m survai.main --selftest-multi
.venv/bin/python -m survai.main --eval-reid
```

Use `--record takes/demo.mp4` in live mode to write one MP4 per camera. Replay uses the same calibration and mirror settings as the recording. For separately recorded clips, trim them to a common start and keep both running through the exit grace period. Run with two cameras first and read the per-camera FPS on the dashboard. Adjust `image_size`, `fusion.tick_hz`, or `sample_every` if needed.

Alert photos and clips expire after two days by default. Set `evidence_retention_days` in your YAML profile to change it. Cleanup checks file age on startup and hourly while the demo runs. It keeps the JSONL history and raw webcam recordings.

For replay, replace `--camera 0` with `--source backup.mp4` and optionally add `--headless`. The dashboard stays open when replay ends. Press Ctrl+C to exit.

Run with zero credentials to log a preview of the WhatsApp message. To enable text delivery, copy `.env.example` to `.env`, fill in the Twilio account credentials and both `whatsapp:+…` addresses, and pass `--whatsapp`. Evidence stays on the local machine. For a sandbox test, join the sandbox and open a messaging session from the recipient phone before triggering an alert. [Twilio WhatsApp Sandbox](https://www.twilio.com/docs/whatsapp/sandbox)
