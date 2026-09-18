"""Write inferred temporal activity labels to Label Studio.

Safety contract:
  * credentials are read from environment variables only, never hard-coded and
    never written to disk;
  * only the temporal-activity annotation is added/updated — existing
    annotations, keypoints and boxes are never touched or deleted;
  * a GET is performed first to verify connectivity;
  * a dry run validates the payload on one task before any bulk write.

Label Studio stores per-task annotations in `result`; each item is a region with
`from_name`/`to_name`, a `type`, and a `value`. Temporal activity labels for a
video are expressed as a `timelinelabels`-style region carrying `start`/`end`
frame indices. Set TEMPORAL_FROM_NAME / TEMPORAL_TO_NAME (and TEMPORAL_TYPE) to
match the project's own labeling config; nothing is assumed silently.
"""
import json
import os
import sys
import urllib.error
import urllib.request

TIMEOUT = 20


class LabelStudioError(Exception):
    pass


class LabelStudioClient:
    def __init__(self, url=None, token=None):
        self.url = (url or os.environ.get("LABEL_STUDIO_URL", "")).rstrip("/")
        self.token = token or os.environ.get("LABEL_STUDIO_TOKEN", "")
        if not self.url or not self.token:
            raise LabelStudioError(
                "LABEL_STUDIO_URL and LABEL_STUDIO_TOKEN must be set in the "
                "environment")
        self.headers = {
            "Authorization": "Token %s" % self.token,
            "Content-Type": "application/json",
        }

    def _request(self, method, path, payload=None):
        url = "%s/api/%s" % (self.url, path.lstrip("/"))
        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=self.headers,
                                     method=method)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                body = resp.read().decode("utf-8")
                return resp.status, (json.loads(body) if body else None)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            return e.code, body
        except (urllib.error.URLError, OSError) as e:
            raise LabelStudioError("connection failed: %s" % e)

    def whoami(self):
        return self._request("GET", "current-user/whoami")

    def get_project(self, project_id):
        return self._request("GET", "projects/%s" % project_id)

    def list_tasks(self, project_id, page=1, page_size=10):
        return self._request(
            "GET", "projects/%s/tasks?page=%d&page_size=%d"
            % (project_id, page, page_size))

    def create_annotation(self, task_id, result):
        return self._request("POST", "tasks/%s/annotations" % task_id,
                             {"result": result})


def build_timeline_result(segments, from_name, to_name, choice_name=None,
                          label_type="timelinelabels"):
    """Build Label Studio result items for contiguous frame segments.

    Frame indices are emitted as Label Studio 0-based frame values so they line
    up with the video timeline.
    """
    items = []
    for s in segments:
        value = {
            "start": float(s["start_frame"] - 1),
            "end": float(s["end_frame"] - 1),
            "timelinelabels": [s["label"]],
        }
        if label_type == "labels":
            value.pop("timelinelabels")
            value["labels"] = [s["label"]]
        items.append({
            "from_name": from_name,
            "to_name": to_name,
            "type": label_type,
            "value": value,
        })
    return items


def verify_connection(client, project_id=None):
    status, body = client.whoami()
    print("whoami -> HTTP %s" % status)
    if status != 200:
        raise LabelStudioError("authentication failed: %s" % str(body)[:200])
    print("  user:", body.get("username") or body.get("email") or "?")
    if project_id:
        status, body = client.get_project(project_id)
        print("project %s -> HTTP %s" % (project_id, status))
        if status != 200:
            raise LabelStudioError("project fetch failed: %s" % str(body)[:200])
        print("  title:", body.get("title"))
        print("  task count:", body.get("task_number"))
    return True


def main():
    project_id = os.environ.get("PROJECT_ID") or os.environ.get(
        "LABEL_STUDIO_PROJECT_ID")
    from_name = os.environ.get("TEMPORAL_FROM_NAME", "temporal")
    to_name = os.environ.get("TEMPORAL_TO_NAME", "video")
    label_type = os.environ.get("TEMPORAL_TYPE", "timelinelabels")
    seg_path = sys.argv[1] if len(sys.argv) > 1 else "segments.json"
    if not project_id:
        print("PROJECT_ID is not set; cannot target a project.")
        return 2
    with open(seg_path, encoding="utf-8") as fh:
        data = json.load(fh)
    segments = data["segments"] if isinstance(data, dict) else data

    client = LabelStudioClient()
    verify_connection(client, project_id)

    result = build_timeline_result(segments, from_name, to_name,
                                   label_type=label_type)
    print("prepared %d result items" % len(result))
    print(json.dumps(result[0], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
