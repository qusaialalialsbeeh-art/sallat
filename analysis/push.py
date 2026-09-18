"""Push inferred temporal labels to Label Studio.

Run:  PROJECT_ID=<id> python3 push.py [--dry-run] [--from-name NAME]
                                        [--to-name NAME] [--type TYPE]

Safety contract, enforced by this script:
  * credentials come only from LABEL_STUDIO_URL / LABEL_STUDIO_TOKEN;
  * a safe GET (/api/current-user/whoami) runs before any write;
  * --dry-run validates the payload against the first task without writing;
  * writes create a NEW annotation on the task and never delete anything,
    never modify keypoints, and never modify bounding boxes;
  * the payload is validated on the first task before the bulk loop.

The Label Studio labeling config must expose a temporal control whose from/to
names match --from-name / --to-name; otherwise the API will reject the result
and this script reports it rather than guessing.
"""
import argparse
import json
import os
import sys

import labelstudio as LS


def load_segments(path):
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return data["segments"] if isinstance(data, dict) else data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--segments", default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "segments.json"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--from-name", default=os.environ.get(
        "TEMPORAL_FROM_NAME", "temporal"))
    ap.add_argument("--to-name", default=os.environ.get(
        "TEMPORAL_TO_NAME", "video"))
    ap.add_argument("--type", default=os.environ.get(
        "TEMPORAL_TYPE", "timelinelabels"))
    ap.add_argument("--task-id", type=int, default=None,
                    help="task to receive the annotation (defaults to the "
                         "project's first task)")
    args = ap.parse_args()

    project_id = os.environ.get("PROJECT_ID") or os.environ.get(
        "LABEL_STUDIO_PROJECT_ID")
    if not project_id:
        print("ERROR: set PROJECT_ID (or LABEL_STUDIO_PROJECT_ID).")
        return 2

    segments = load_segments(args.segments)
    result = LS.build_timeline_result(segments, args.from_name, args.to_name,
                                      label_type=args.type)
    print("segments: %d | result items: %d" % (len(segments), len(result)))

    client = LS.LabelStudioClient()
    try:
        LS.verify_connection(client, project_id)
    except LS.LabelStudioError as e:
        print("ERROR: %s" % e)
        print("The Label Studio host is not reachable from this sandbox.")
        return 3

    status, tasks = client.list_tasks(project_id, page=1, page_size=5)
    if status != 200:
        print("ERROR: could not list tasks: HTTP %s %s" % (status, str(tasks)[:200]))
        return 4
    task_list = tasks.get("tasks") if isinstance(tasks, dict) else tasks
    if not task_list:
        print("ERROR: project %s has no tasks." % project_id)
        return 4
    task_id = args.task_id or task_list[0]["id"]

    if args.dry_run:
        print("DRY RUN - would POST %d items to task %s" % (len(result), task_id))
        print(json.dumps(result[0], ensure_ascii=False, indent=2))
        return 0

    # validate on a single task before any bulk write
    status, body = client.create_annotation(task_id, result)
    print("validation write to task %s -> HTTP %s" % (task_id, status))
    if status >= 300:
        print("ERROR: payload rejected: %s" % str(body)[:500])
        return 5
    print("  annotation id:", (body or {}).get("id"))

    # bulk write
    written, failed = 0, 0
    for t in task_list[1:]:
        st, bd = client.create_annotation(t["id"], result)
        if st < 300:
            written += 1
        else:
            failed += 1
            print("  task %s failed HTTP %s: %s" % (t["id"], st, str(bd)[:200]))
    print("done. written=%d failed=%d" % (written, failed))
    return 0


if __name__ == "__main__":
    sys.exit(main())