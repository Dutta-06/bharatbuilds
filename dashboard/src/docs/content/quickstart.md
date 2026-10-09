# Quickstart

Place your first job and read its receipt. This takes about two minutes and needs no sign-in.

## 1. Describe the job

Open **Submit**. Leave the defaults, or set:

- **GPU-hours:** `4`
- **Finish within:** `24` hours (the preset buttons set common values)
- **Optimise for:** the slider, with 50% water and 50% carbon as the default

The panel on the right shows an **estimate**. It names the best region and hour for your settings and compares water and carbon with running now in the comparison region. It updates as you change the form.

## 2. Place the job

Press **Place job**. You land on the job page, which shows:

- the **verdict**, a plain-language explanation such as "Run in eu-north-1 starting Fri 08:00, finishing before the deadline. Compared with running now in ap-south-1: 88% less water and 97% less CO₂";
- a **progress strip** (placed, waiting, running, done);
- the **water and carbon figures** with their uncertainty ranges;
- the **options considered**, so you can see what the alternatives would have cost.

## 3. Let it run

The job waits for its start hour. While it waits you can press **Move to the better slot** if a better window has opened, and you will get an email if one does. The [Queue](#/docs/guide-queue) lists every job and its status.

## 4. Read the receipt

When the job has run, the job page shows the final receipt. Open **Share, export or print** to copy a link, download JSON or CSV, or print it.

## Using the API instead

Everything in the app is available over HTTP. This places the same job from a terminal:

```bash
curl -X POST "$API/jobs" -H 'content-type: application/json' \
  -d '{"gpu_hours": 4, "deadline_h": 24, "submit_region": "ap-south-1", "name": "nightly fine-tune"}'
```

The response includes a `job_id`. Fetch its receipt with `GET $API/jobs/<job_id>/receipt`. See the [API reference](#/docs/api).

## Next

- [How placement works](#/docs/how-placement-works)
- [What the cost number means](#/docs/cost-index)
- [Frequently asked questions](#/docs/faq)
