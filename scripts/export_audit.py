import json
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import create_app


if __name__ == '__main__':
    app = create_app()
    events = []
    for event in app.state.audit_logger.list_events():
        events.append(
            {
                'timestamp': event.timestamp.isoformat(),
                'transaction_id': event.transaction_id,
                'event_type': event.event_type,
                'actor': event.actor,
                'status': event.status,
                'reason': event.reason,
                'metadata': event.metadata,
            }
        )
    print(json.dumps(events, indent=2, ensure_ascii=False))
