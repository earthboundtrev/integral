"""Legacy entry point — launches Integral (personal_dev_tracker.py)."""

import sys


def main() -> None:
    from personal_dev_tracker import main as integral_main

    integral_main()


if __name__ == "__main__":
    print("Launching Integral...", file=sys.stderr)
    main()
