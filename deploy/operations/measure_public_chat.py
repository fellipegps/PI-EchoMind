"""One bounded synthetic public-chat batch, with no credentials or session access.

Only targets the existing EchoMind HTTPS API. Never prints response text.
Run phases individually and check host headroom before increasing concurrency.
"""
from __future__ import annotations

import argparse
import concurrent.futures
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import statistics
import threading
import time
import unicodedata
import urllib.error
import urllib.request

API = 'https://echomind-api.duckdns.org'
QUESTIONS = (
    'Qual e o codigo de conferencia do programa sintetico de capacidade?',
    'No documento de capacidade, qual identificador deve ser usado na conferencia?',
    'Informe o codigo de conferencia e o horario de atendimento do teste sintetico.',
    'Segundo o documento sintetico, qual e o codigo CAPACITY usado para conferir o teste?',
)


def marker_found(body, marker):
    # Generated prose may use a typographic hyphen in an otherwise exact code.
    def normalize(value):
        return ''.join('-' if unicodedata.category(char) == 'Pd' else char
                       for char in unicodedata.normalize('NFKC', value)).casefold()
    return normalize(marker) in normalize(body)


def request_one(index, url, marker, barrier, *, mixed_questions=False, fixed_question_index=0):
    barrier.wait(timeout=15)
    started = time.perf_counter()
    result = {'request': index + 1, 'status': None, 'bytes': 0,
              'expected_marker_found': False, 'first_byte_seconds': None}
    try:
        question = QUESTIONS[index] if mixed_questions else QUESTIONS[fixed_question_index]
        request = urllib.request.Request(url, data=json.dumps({'message': question}).encode(),
            headers={'Content-Type': 'application/json', 'User-Agent': 'EchoMind-Capacity-Check/1'}, method='POST')
        with urllib.request.urlopen(request, timeout=60) as response:
            result['status'] = response.status
            first = response.read(1)
            result['first_byte_seconds'] = round(time.perf_counter() - started, 3) if first else None
            body = first + response.read(65536)
            result['bytes'] = len(body)
            result['expected_marker_found'] = marker_found(body.decode('utf-8', errors='replace'), marker)
    except urllib.error.HTTPError as error:
        result['status'] = error.code
        result['error'] = 'http_error'
        error.close()
    except (OSError, TimeoutError, urllib.error.URLError):
        result['error'] = 'network_or_timeout'
    result['duration_seconds'] = round(time.perf_counter() - started, 3)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public-slug', required=True)
    parser.add_argument('--concurrency', type=int, choices=(1, 2, 4), required=True)
    parser.add_argument('--expected-marker', default='CAPACITY-20261019')
    parser.add_argument('--mixed-questions', action='store_true', help='Vary question wording; not a controlled concurrency comparison')
    parser.add_argument('--question-index', type=int, choices=(1, 2, 3, 4), default=1)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'[a-z0-9-]{1,160}', args.public_slug):
        parser.error('Require an existing public institution slug.')
    barrier = threading.Barrier(args.concurrency)
    started = datetime.now(timezone.utc).isoformat()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        futures = [executor.submit(request_one, index, f'{API}/public/{args.public_slug}/chat',
                                   args.expected_marker, barrier, mixed_questions=args.mixed_questions,
                                   fixed_question_index=args.question_index - 1)
                   for index in range(args.concurrency)]
        results = [future.result() for future in futures]
    report = {'started_at': started, 'ended_at': datetime.now(timezone.utc).isoformat(),
              'api_origin': API, 'concurrency': args.concurrency, 'requests': results,
              'question_set': 'mixed' if args.mixed_questions else 'fixed',
              'question_index': None if args.mixed_questions else args.question_index,
              'mean_duration_seconds': round(statistics.mean(r['duration_seconds'] for r in results), 3),
              'max_duration_seconds': max(r['duration_seconds'] for r in results),
              'all_expected_answers': all(r['status'] == 200 and r['expected_marker_found'] for r in results),
              'scope': 'Single synthetic batch, including client network/TLS and upstream services; not sustained capacity or a percentile estimate'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report))
    raise SystemExit(0 if report['all_expected_answers'] else 1)


if __name__ == '__main__':
    main()
