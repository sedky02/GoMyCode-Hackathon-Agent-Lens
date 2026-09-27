"""Group failure findings into issues with embeddings + clustering, then rank them."""

import json
import math
from collections import Counter

SEVERITY_WEIGHT = {"high": 1.0, "medium": 0.6, "low": 0.3}
SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2}
DISTANCE_THRESHOLD = 0.3
TITLES = {
    "wrong_record": "Wrong record: agent queried a different entity than the user asked for",
    "unsupported_success": "Unsupported success: agent claimed success although the tool failed",
    "no_progress": "No progress: agent repeated the same search without refining it",
    "incomplete_request": "Incomplete request: part of the request was never done but was claimed",
    "repeated_question": "Repeated question: agent re-asked for information the user already gave",
}

_model = None


def embed(texts):
    global _model
    try:
        if _model is None:
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        return _model.encode(texts, normalize_embeddings=True)
    except Exception as exc:
        print(f"[grouping] sentence-transformers unavailable ({exc}); falling back to TF-IDF")
        from sklearn.feature_extraction.text import TfidfVectorizer
        return TfidfVectorizer().fit_transform(texts).toarray()


def cluster(vectors):
    if len(vectors) == 1:
        return [0]
    from sklearn.cluster import AgglomerativeClustering
    model = AgglomerativeClustering(n_clusters=None, metric="cosine", linkage="average",
                                    distance_threshold=DISTANCE_THRESHOLD)
    return list(model.fit_predict(vectors))


def build_issues(conn):
    findings = [dict(r) for r in conn.execute("SELECT * FROM findings")]
    conn.execute("DELETE FROM issues")
    if not findings:
        conn.commit()
        return []

    groups = []
    by_type = {}
    for f in findings:
        by_type.setdefault(f["failure_type"], []).append(f)
    for ftype, members in by_type.items():
        labels = cluster(embed([m["signature"] for m in members]))
        clusters = {}
        for m, label in zip(members, labels):
            clusters.setdefault(label, []).append(m)
        for members_in_cluster in clusters.values():
            groups.append((ftype, members_in_cluster, len(clusters) > 1))

    max_n = max(len({m["session_id"] for m in g[1]}) for g in groups)
    issues = []
    for ftype, members, split in groups:
        sessions = {m["session_id"] for m in members}
        tools = [t for t, _ in Counter(m["tool"] for m in members if m["tool"]).most_common()]
        severity = max((m["severity"] for m in members), key=SEVERITY_RANK.get)
        avg_conf = sum(m["confidence"] for m in members) / len(members)
        priority = 100 * math.sqrt(len(sessions) / max_n) * SEVERITY_WEIGHT[severity] * avg_conf
        title = TITLES.get(ftype, ftype)
        if split and tools:
            title += f" ({tools[0]})"
        issues.append({"title": title, "failure_type": ftype, "severity": severity,
                       "session_count": len(sessions), "avg_confidence": round(avg_conf, 3),
                       "priority": round(priority, 1), "tools": tools,
                       "finding_ids": [m["finding_id"] for m in members]})

    issues.sort(key=lambda i: -i["priority"])
    for issue_id, issue in enumerate(issues, start=1):
        issue["issue_id"] = issue_id
        conn.execute("INSERT INTO issues VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                     (issue_id, issue["title"], issue["failure_type"], issue["severity"], issue["session_count"],
                      issue["avg_confidence"], issue["priority"], json.dumps(issue["tools"]),
                      json.dumps(issue["finding_ids"])))
        conn.executemany("UPDATE findings SET issue_id = ? WHERE finding_id = ?",
                         [(issue_id, fid) for fid in issue["finding_ids"]])
    conn.commit()
    return issues
