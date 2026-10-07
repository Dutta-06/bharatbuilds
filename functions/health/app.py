"""Placeholder function so `sam build` has something to build (Step 0)."""

import json


def handler(event, context):
    return {"statusCode": 200, "body": json.dumps({"ok": True})}
