# Walk-out detection demo

The MacBook webcam demo uses anonymous person tracks to flag a possible walk-out. The preview mirrors the camera. All zone coordinates refer to that mirrored view. Payment is simulated with the pay zone or the `p` key. A future Toast, Square, or Clover integration can supply a payment confirmation once a POS check has been associated with a visit.

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

When one person briefly blocks another, the tracker uses position, motion, and coarse clothing colors to recover their number and visit state. The default recovery window is five seconds from when the covered person was last seen. Set `occlusion_seconds` in the YAML profile to adjust it. Similar clothing and longer overlaps can still cause tracking mistakes.

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

Open [the local dashboard](http://127.0.0.1:8765). An unpaid exit plays a system sound on macOS and adds a card with an annotated photo. The clip link appears after the two-second post-roll and encode. The H.264 MP4 includes up to eight seconds before the alert and two seconds after it, bounded by available camera or replay footage. The annotated JPEGs, clips, and `alerts.jsonl` are saved to `alerts/` by default. Use `--output` to choose another directory.

The count in the top right starts at **0 alerts** each time the app starts. Use **Delete** on a false alarm to remove it from the session's alert history and count. Its saved evidence and JSONL record remain on disk under the usual retention settings.

**Active visits** shows each tracked guest from the first time the camera sees them. When a guest pays, the dashboard shows a cropped photo from an earlier frame. The local process holds active profiles and photos in memory and removes them when the visit ends or the demo resets. The walk-out alert history has its own evidence retention.

## Hosted demo

Vercel builds the dashboard with `node scripts/build-dashboard.mjs`. Add a simulated guest, mark them paid to reveal the earlier sample image, then send them out to remove the visit. A simulated unpaid exit creates a deletable alert. The hosted demo uses browser memory and synthetic images. Start the local Python app to use a real camera.

Alert photos and clips expire after two days by default. Set `evidence_retention_days` in your YAML profile to change it. Cleanup checks file age on startup and hourly while the demo runs. It keeps the JSONL history and raw webcam recordings.

For replay, replace `--camera 0` with `--source backup.mp4` and optionally add `--headless`. The dashboard stays open when replay ends. Press Ctrl+C to exit.

Run with zero credentials to log a preview of the WhatsApp message. To enable text delivery, copy `.env.example` to `.env`, fill in the Twilio account credentials and both `whatsapp:+…` addresses, and pass `--whatsapp`. Evidence stays on the local machine. For a sandbox test, join the sandbox and open a messaging session from the recipient phone before triggering an alert. [Twilio WhatsApp Sandbox](https://www.twilio.com/docs/whatsapp/sandbox)
