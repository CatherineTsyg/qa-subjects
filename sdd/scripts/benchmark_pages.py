#!/usr/bin/env python
"""Замер p95 времени ответа публичных страниц (stdlib: urllib + ThreadPoolExecutor)."""

import argparse
import re
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.request import urlopen

SUBJECT_RE = re.compile(r'href="/subjects/(\d+)/"')
QUESTION_RE = re.compile(r'href="/questions/(\d+)/"')


def fetch(url, timeout):
    started = time.perf_counter()
    with urlopen(url, timeout=timeout) as response:
        response.read()
        status = response.status
    elapsed_ms = (time.perf_counter() - started) * 1000
    return elapsed_ms, status


def discover_ids(base_url, timeout):
    with urlopen(base_url, timeout=timeout) as response:
        html = response.read().decode("utf-8")
    subject_ids = SUBJECT_RE.findall(html)
    if not subject_ids:
        return None, None

    subject_url = f"{base_url.rstrip('/')}/subjects/{subject_ids[0]}/"
    with urlopen(subject_url, timeout=timeout) as response:
        subject_html = response.read().decode("utf-8")
    question_ids = QUESTION_RE.findall(subject_html)
    question_id = question_ids[0] if question_ids else None
    return subject_ids[0], question_id


def percentile(values, ratio):
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round((len(ordered) - 1) * ratio)))
    return ordered[index]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8001")
    parser.add_argument("--threads", type=int, default=100)
    parser.add_argument("--requests", type=int, default=200, help="запросов на URL")
    parser.add_argument("--timeout", type=float, default=30.0)
    options = parser.parse_args()

    subject_id, question_id = discover_ids(options.base_url, options.timeout)
    if subject_id is None:
        raise SystemExit("Не найдено ни одного предмета: сначала выполните seed_demo.")

    base = options.base_url.rstrip("/")
    targets = [
        ("Список предметов", f"{base}/"),
        ("Страница предмета", f"{base}/subjects/{subject_id}/"),
    ]
    if question_id is not None:
        targets.append(("Страница вопроса", f"{base}/questions/{question_id}/"))

    results = {name: [] for name, _ in targets}
    statuses = {name: set() for name, _ in targets}
    errors = []

    def run(target):
        name, url = target
        try:
            elapsed, status = fetch(url, options.timeout)
            results[name].append(elapsed)
            statuses[name].add(status)
        except Exception as exc:  # noqa: BLE001 - печатаем причину в отчёте
            errors.append(f"{name}: {exc}")

    tasks = [target for target in targets for _ in range(options.requests)]
    with ThreadPoolExecutor(max_workers=options.threads) as pool:
        list(pool.map(run, tasks))

    print(f"Потоков: {options.threads}; запросов на URL: {options.requests}")
    print(f"{'Страница':<20} {'Запросов':>9} {'p50, мс':>9} {'p95, мс':>9} {'Статусы'}")
    for name, _ in targets:
        values = results[name]
        print(
            f"{name:<20} {len(values):>9} "
            f"{percentile(values, 0.50):>9.1f} {percentile(values, 0.95):>9.1f} "
            f"{sorted(statuses[name])}"
        )
    if errors:
        print("Ошибки:")
        for error in errors[:10]:
            print(f"- {error}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
