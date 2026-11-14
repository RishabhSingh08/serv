import argparse
import logging
from pathlib import Path

from .config import WalkoutConfig, load_walkout_config
from .detectors.walkout import VisitState, WalkoutDetector, WalkoutEvent
from .synthetic import demo_tracks

LOG = logging.getLogger(__name__)
DEMO_CONFIG = Path(__file__).with_name("walkout.demo.yaml")
LOCAL_CONFIG = Path("walkout.local.yaml")


def selftest(config: WalkoutConfig) -> bool:
    passed = True
    for name, paid, expected in (("Unpaid exit", False, 1), ("Paid exit", True, 0)):
        detector = WalkoutDetector(config)
        events: list[WalkoutEvent] = []
        states: set[VisitState] = set()
        for now, tracks in demo_tracks(paid):
            events.extend(detector.update(tracks, now))
            states.update(visit.state for visit in detector.visits.values())
        ok = (
            VisitState.DINING in states
            and (VisitState.PAID in states) == paid
            and len(events) == expected
            and all(event.exit_type == "track_lost" for event in events)
        )
        LOG.info(
            "%s %s: %d alert(s), expected %d",
            "PASS" if ok else "FAIL", name, len(events), expected,
        )
        passed &= ok
    return passed


def main() -> int:
    parser = argparse.ArgumentParser(description="MacBook walk-out detection demo")
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--selftest", action="store_true", help="Run synthetic demo takes")
    modes.add_argument("--list-cameras", action="store_true", help="Find usable camera indices")
    modes.add_argument("--demo-mode", action="store_true", help="Run the mirrored preview")
    modes.add_argument("--calibrate", action="store_true", help="Draw and save zones in the mirrored preview")
    sources = parser.add_mutually_exclusive_group()
    sources.add_argument("--camera", type=int, default=0)
    sources.add_argument("--source", type=Path, help="Replay a recorded video")
    parser.add_argument("--config", type=Path, help="Use a YAML config (default: walkout.local.yaml if present)")
    parser.add_argument("--weights", help="Use a local YOLO weights file")
    parser.add_argument("--record", type=Path, help="Save the raw camera feed to an MP4 file")
    parser.add_argument("--headless", action="store_true", help="Run without the preview window")
    parser.add_argument("--dashboard", action="store_true", help="Serve the local dashboard")
    parser.add_argument("--port", type=int, default=8765, help="Dashboard port")
    parser.add_argument("--output", type=Path, default=Path("alerts"), help="Alert evidence directory")
    parser.add_argument("--whatsapp", action="store_true", help="Enable Twilio delivery with configured credentials")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if args.selftest:
        return 0 if selftest(load_walkout_config(DEMO_CONFIG)) else 1
    if args.list_cameras:
        from .preview import list_cameras

        return list_cameras()
    if args.camera < 0:
        parser.error("--camera must be non-negative")
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    if args.calibrate and (args.headless or args.dashboard or args.record or args.whatsapp):
        parser.error("--calibrate uses a separate preview window")
    destination = args.config or LOCAL_CONFIG
    use_default = (args.calibrate or args.config is None) and not destination.exists()
    config_path = DEMO_CONFIG if use_default else destination
    source = str(args.source.resolve() if args.source else args.camera)
    try:
        config = load_walkout_config(config_path)
        if args.calibrate:
            from .calibrate import run_calibration

            return run_calibration(config, source, destination)
        from .preview import run_preview

        return run_preview(
            config, source, args.weights, args.record, args.headless,
            output=args.output, dashboard_port=args.port if args.dashboard else None, whatsapp=args.whatsapp,
        )
    except (RuntimeError, OSError, ValueError) as exc:
        LOG.error("%s", exc)
        return 1
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
