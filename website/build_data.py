#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يولّد بيانات موقع المغني من مصادر المشروع نفسها فلا تتقادم:

- data/changelog.json من changes.md (سجل إصدارات التطبيق).
- data/catalog.json يُنشأ أول مرة ببنية فارغة ثم يُحرَّر يدويًا؛
  لا يُستبدل إن وُجد، لكن تُحدَّث فيه نسخة المثبّتات من آخر إصدار.

التشغيل: python3 website/build_data.py
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

CATEGORIES = ("projects", "chats", "manuscripts", "agents",
              "reading", "tools", "patterns")


def parse_changelog():
    path = os.path.join(ROOT, "changes.md")
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    releases = []
    for m in re.finditer(r"##\s+(1\.\d+\.\d+)[^\n]*\n(.*?)(?=\n##\s+1\.|\Z)",
                         text, re.S):
        notes = [ln.strip()[2:].strip() for ln in m.group(2).splitlines()
                 if ln.strip().startswith("- ")]
        if notes:
            releases.append({"version": m.group(1), "notes": notes})
    return releases


def main():
    releases = parse_changelog()
    latest = releases[0]["version"] if releases else ""
    os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
    with open(os.path.join(HERE, "data", "changelog.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"releases": releases}, fh, ensure_ascii=False, indent=2)

    catalog_path = os.path.join(HERE, "data", "catalog.json")
    if os.path.exists(catalog_path):
        with open(catalog_path, encoding="utf-8") as fh:
            catalog = json.load(fh)
    else:
        catalog = {"installers": [], "categories": {c: [] for c in CATEGORIES}}
    for cat in CATEGORIES:
        catalog.setdefault("categories", {}).setdefault(cat, [])
        os.makedirs(os.path.join(HERE, "files", cat), exist_ok=True)
    os.makedirs(os.path.join(HERE, "files", "downloads"), exist_ok=True)
    if not catalog.get("installers"):
        catalog["installers"] = [
            {"key": "win", "name": "المغني لويندوز",
             "file": "files/downloads/almoghni.exe",
             "version": latest, "size": "", "date": "", "downloads": 0},
            {"key": "mac", "name": "المغني لماك",
             "file": "files/downloads/almoghni.dmg",
             "version": latest, "size": "", "date": "", "downloads": 0},
        ]
    else:
        for it in catalog["installers"]:
            it["version"] = latest
    with open(catalog_path, "w", encoding="utf-8") as fh:
        json.dump(catalog, fh, ensure_ascii=False, indent=2)
    print(f"آخر إصدار {latest} · {len(releases)} إصدارًا في السجل")


if __name__ == "__main__":
    main()
