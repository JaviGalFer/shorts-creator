#!/usr/bin/env python3

import argparse
import json
from datetime import datetime
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description='Review a rendered video job')
    parser.add_argument('metadata_path', help='Path to metadata JSON')
    parser.add_argument('decision', choices=['approve', 'reject'])
    parser.add_argument('--message', '-m', default='', help='Review comment')
    args = parser.parse_args()

    metadata_path = Path(args.metadata_path).resolve()
    data = json.loads(metadata_path.read_text())

    if data.get('status') not in ('RENDERED', 'REVIEW_PENDING'):
        print(f"Error: Job status is '{data.get('status')}', expected RENDERED or REVIEW_PENDING")
        return 1

    new_status = 'APPROVED' if args.decision == 'approve' else 'REJECTED'

    data['status'] = new_status
    data['review'] = {
        'status': new_status,
        'reviewedAt': datetime.utcnow().isoformat() + 'Z',
        'message': args.message,
    }
    data['updatedAt'] = datetime.utcnow().isoformat() + 'Z'

    metadata_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'jobId': data['jobId'], 'status': new_status, 'review': data['review']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
