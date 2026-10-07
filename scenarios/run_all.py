import json

from scenarios.disconnect_scenario import run as run_disconnect
from scenarios.invalid_amount import run as run_invalid_amount
from scenarios.invalid_order import run as run_invalid_order
from scenarios.normal_flow import run as run_normal
from scenarios.replay_attack import run as run_replay
from scenarios.restart_scenario import run as run_restart
from scenarios.tampered_message import run as run_tampered
from scenarios.timeout_scenario import run as run_timeout


if __name__ == '__main__':
    results = [
        run_normal(),
        run_replay(),
        run_tampered(),
        run_invalid_amount(),
        run_invalid_order(),
        run_timeout(),
        run_disconnect(),
        run_restart(),
    ]
    print(json.dumps(results, indent=2, ensure_ascii=False))
