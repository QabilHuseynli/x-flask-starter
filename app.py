#!/usr/bin/env python3
"""
Flask + X(Twitter) API starter (ayrı HTML template, CSV export, sayfalama, rate-limit bilgisi)
Endpoints:
  - /api/search?q=...&limit=10[&next_token=...][&format=csv&pages=3]
  - /api/user/<username>?with_tweets=true&limit=5[&next_token=...][&format=csv&pages=3]
  - /ui  -> mini HTML arayüz
"""
from flask import Flask, request, jsonify, Response, render_template
import os, time, json, hashlib, csv, io
from datetime import datetime, timezone
import httpx
from dotenv import load_dotenv

# --- Config & boot ---
load_dotenv()
X_BEARER_TOKEN = os.getenv("X_BEARER_TOKEN")
API_BASE       = os.getenv("API_BASE", "https://api.x.com/2")
CACHE_TTL      = int(os.getenv("CACHE_TTL", "60"))
PORT           = int(os.getenv("PORT", "5000"))

if not X_BEARER_TOKEN:
    raise SystemExit("X_BEARER_TOKEN missing. Add it to .env")

app = Flask(__name__)

# --- Tiny success-only in-memory cache ---
_CACHE = {}
def _cache_key(url: str, params: dict) -> str:
    raw = url + "|" + json.dumps(params or {}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def _cached_get(client: httpx.Client, url: str, headers: dict, params: dict, cache_ttl: int = CACHE_TTL):
    key = _cache_key(url, params)
    now = time.time()
    if cache_ttl > 0:
        hit = _CACHE.get(key)
        if hit and hit["exp"] > now:
            return hit["status"], hit["json"], hit["headers"]

    resp = client.get(url, headers=headers, params=params)
    try:
        body = resp.json()
    except Exception:
        body = {"text": resp.text}

    if cache_ttl > 0 and resp.status_code == 200:
        _CACHE[key] = {
            "exp": now + cache_ttl,
            "status": resp.status_code,
            "json": body,
            "headers": dict(resp.headers),
        }
    return resp.status_code, body, resp.headers

# --- Helpers ---
def _auth_headers():
    return {"Authorization": f"Bearer {X_BEARER_TOKEN}"}

def _safe_int(val, default, min_v=None, max_v=None):
    try:
        iv = int(val)
    except Exception:
        iv = default
    if min_v is not None: iv = max(iv, min_v)
    if max_v is not None: iv = min(iv, max_v)
    return iv

def _hydrate_tweets(data: dict):
    """Attach author/media includes to each tweet (varsa)."""
    if not isinstance(data, dict): return data
    tweets   = data.get("data", [])
    includes = data.get("includes", {})
    users = {u.get("id"): u for u in includes.get("users", [])}
    media = {m.get("media_key"): m for m in includes.get("media", [])}
    for tw in tweets:
        a = users.get(tw.get("author_id"))
        if a: tw["author"] = a
        mkeys = (tw.get("attachments") or {}).get("media_keys") or []
        if mkeys:
            tw["media"] = [media[k] for k in mkeys if k in media]
    return data

def _rate_info(resp_or_headers):
    headers = getattr(resp_or_headers, "headers", None) or resp_or_headers or {}
    reset = headers.get("x-rate-limit-reset")
    if reset and str(reset).isdigit():
        reset_dt = datetime.fromtimestamp(int(reset), tz=timezone.utc)
        secs = max(0, int(reset) - int(time.time()))
    else:
        reset_dt, secs = None, None
    return {
        "limit": headers.get("x-rate-limit-limit"),
        "remaining": headers.get("x-rate-limit-remaining"),
        "reset_epoch": reset,
        "reset_utc": reset_dt.isoformat() if reset_dt else None,
        "seconds_until_reset": secs,
    }

# --- CSV helpers ---
CSV_TWEET_FIELDS = [
    "tweet_id","created_at","author_username","author_name","author_id",
    "text","lang","like_count","retweet_count","reply_count","quote_count",
    "bookmark_count","impression_count","possibly_sensitive",
    "media_urls","media_types","referenced_types","referenced_ids",
]

def _tweets_block_to_rows(block: dict):
    rows = []
    if not isinstance(block, dict): return rows
    data     = block.get("data", []) or []
    includes = block.get("includes", {}) or {}
    users = {u.get("id"): u for u in includes.get("users", [])}
    media = {m.get("media_key"): m for m in includes.get("media", [])}
    for t in data:
        a  = t.get("author") or users.get(t.get("author_id")) or {}
        pm = t.get("public_metrics", {}) or {}
        # referenced
        ref = t.get("referenced_tweets") or []
        ref_types = ",".join(str(x.get("type")) for x in ref if x)
        ref_ids   = ",".join(str(x.get("id"))   for x in ref if x)
        # media
        keys  = ((t.get("attachments") or {}).get("media_keys")) or []
        mlist = [media.get(k) for k in keys if k in media]
        m_urls  = ",".join(m.get("url")  for m in mlist if m and m.get("url"))
        m_types = ",".join(m.get("type") for m in mlist if m and m.get("type"))
        rows.append({
            "tweet_id": t.get("id"),
            "created_at": t.get("created_at"),
            "author_username": a.get("username"),
            "author_name": a.get("name"),
            "author_id": t.get("author_id"),
            "text": (t.get("text") or "").replace("\r"," ").replace("\n"," "),
            "lang": t.get("lang"),
            "like_count": pm.get("like_count"),
            "retweet_count": pm.get("retweet_count"),
            "reply_count": pm.get("reply_count"),
            "quote_count": pm.get("quote_count"),
            "bookmark_count": pm.get("bookmark_count"),
            "impression_count": pm.get("impression_count"),
            "possibly_sensitive": t.get("possibly_sensitive"),
            "media_urls": m_urls,
            "media_types": m_types,
            "referenced_types": ref_types,
            "referenced_ids": ref_ids,
        })
    return rows

def _user_to_rows(user: dict):
    if not user: return []
    pm = (user.get("public_metrics") or {})
    fields = [
        "id","username","name","created_at","verified","protected","location","description",
        "followers_count","following_count","tweet_count","listed_count","like_count","media_count"
    ]
    row = {
        "id": user.get("id"),
        "username": user.get("username"),
        "name": user.get("name"),
        "created_at": user.get("created_at"),
        "verified": user.get("verified"),
        "protected": user.get("protected"),
        "location": (user.get("location") or ""),
        "description": (user.get("description") or "").replace("\r"," ").replace("\n"," "),
        "followers_count": pm.get("followers_count"),
        "following_count": pm.get("following_count"),
        "tweet_count": pm.get("tweet_count"),
        "listed_count": pm.get("listed_count"),
        "like_count": pm.get("like_count"),
        "media_count": pm.get("media_count"),
    }
    return fields, [row]

def _rows_to_csv(fieldnames, rows, filename="export.csv"):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        writer.writerow(r)
    data = buf.getvalue()
    return Response(data, mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f"attachment; filename=\"{filename}\""})

# --- Routes ---
@app.get("/")
def root():
    return jsonify({
        "ok": True,
        "service": "x-flask-starter",
        "endpoints": ["/api/search", "/api/user/<username>", "/ui"],
        "cache_ttl": CACHE_TTL,
        "api_base": API_BASE,
    })

@app.get("/ui")
def ui():
    return render_template("ui.html")

@app.get("/api/search")
def search_recent():
    """
    Example:
      /api/search?q=from:nasa moon&limit=10&pages=2&format=csv
    Varsayılan: retweets,replies hariç. exclude= (boş) gönderilirse filtre uygulanmaz.
    """
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"error": "missing query param q"}), 400

    limit      = _safe_int(request.args.get("limit", 10), 10, 10, 100)
    raw_exc    = request.args.get("exclude", None)  # None -> default uygula, "" -> hepsini dahil et
    exclude    = "retweets,replies" if raw_exc is None else raw_exc
    next_token = request.args.get("next_token")
    fmt        = request.args.get("format", "json").lower()
    pages      = _safe_int(request.args.get("pages", 1), 1, 1, 20)

    # build query string
    query = q
    if exclude:
        parts = [e.strip() for e in exclude.split(",") if e.strip()]
        if parts:
            query = f"{q} " + " ".join(f"-is:{p}" for p in parts)

    url = f"{API_BASE}/tweets/search/recent"
    try:
        with httpx.Client(timeout=20.0) as client:
            rows, token, last_body = [], next_token, None
            for _ in range(pages):
                params = {
                    "query": query,
                    "max_results": limit,
                    "tweet.fields": "created_at,public_metrics,lang,possibly_sensitive,entities,referenced_tweets,attachments,author_id",
                    "expansions": "author_id,attachments.media_keys",
                    "user.fields": "name,username,profile_image_url,verified,public_metrics",
                    "media.fields": "type,url,preview_image_url,width,height,alt_text",
                }
                if token:
                    params["pagination_token"] = token

                status, body, headers = _cached_get(client, url, _auth_headers(), params)
                if status != 200:
                    if fmt == "csv" and rows:
                        return _rows_to_csv(CSV_TWEET_FIELDS, rows, "search_partial.csv")
                    return jsonify({"error": "x_api_error", "status": status, "body": body,
                                    "rate_limit": _rate_info(headers)}), status

                block = _hydrate_tweets(body)
                last_body = block
                rows.extend(_tweets_block_to_rows(block))
                token = (block.get("meta") or {}).get("next_token")
                if not token:
                    break

            if fmt == "csv":
                safe_q = q.replace(" ", "_")[:50]
                return _rows_to_csv(CSV_TWEET_FIELDS, rows, f"search_{safe_q or 'query'}.csv")

            return jsonify(last_body)
    except httpx.HTTPError as e:
        return jsonify({"error": "http_error", "detail": str(e)}), 502

@app.get("/api/user/<username>")
def get_user(username):
    """
    Example:
      /api/user/nasa?with_tweets=true&limit=5&pages=3&format=csv
    Timeline 429/403 olursa otomatik 'from:<username>' search fallback.
    """
    username    = username.strip().lstrip("@")
    limit       = _safe_int(request.args.get("limit", 5), 5, 1, 100)
    with_tweets = request.args.get("with_tweets", "false").lower() in ("1", "true", "yes")
    raw_exc     = request.args.get("exclude", None)  # None->default, ""->include all
    exclude     = "retweets,replies" if raw_exc is None else raw_exc
    next_token  = request.args.get("next_token")
    fmt         = request.args.get("format", "json").lower()
    pages       = _safe_int(request.args.get("pages", 1), 1, 1, 20)

    u_params = {"user.fields": "name,username,profile_image_url,verified,protected,created_at,description,location,url,public_metrics"}
    u_url    = f"{API_BASE}/users/by/username/{username}"

    try:
        with httpx.Client(timeout=20.0) as client:
            st, u_body, _ = _cached_get(client, u_url, _auth_headers(), u_params)
            if st != 200:
                return jsonify({"error": "x_api_error", "status": st, "body": u_body}), st

            user = (u_body or {}).get("data")
            if not user:
                return jsonify({"error": "user_not_found", "username": username}), 404

            # CSV profile only?
            if fmt == "csv" and not with_tweets:
                fields, rows = _user_to_rows(user)
                return _rows_to_csv(fields, rows, f"user_{user.get('username') or 'profile'}.csv")

            result = {"user": user}
            if not with_tweets:
                return jsonify(result)

            use_search, rows, token, last_block = False, [], next_token, None
            for _ in range(pages):
                if not use_search:
                    t_params = {
                        "max_results": limit,
                        "tweet.fields": "created_at,public_metrics,lang,possibly_sensitive,entities,referenced_tweets,attachments,author_id",
                        "expansions": "attachments.media_keys,author_id",
                        "user.fields": "name,username,profile_image_url,verified,public_metrics",
                        "media.fields": "type,url,preview_image_url,width,height,alt_text",
                    }
                    if exclude:                # BOŞSA göndermiyoruz (hepsi dahil)
                        t_params["exclude"] = exclude
                    if token:
                        t_params["pagination_token"] = token

                    t_url = f"{API_BASE}/users/{user['id']}/tweets"
                    ts, tb, th = _cached_get(client, t_url, _auth_headers(), t_params)

                    if ts == 200:
                        block = _hydrate_tweets(tb)
                        last_block = block
                        rows.extend(_tweets_block_to_rows(block))
                        token = (block.get("meta") or {}).get("next_token")
                        if not token:
                            break
                    elif ts in (429, 403):
                        use_search = True
                        token = next_token   # reset for search path
                    else:
                        if fmt == "csv" and rows:
                            return _rows_to_csv(CSV_TWEET_FIELDS, rows, f"user_{user.get('username')}_partial.csv")
                        result["tweets_error"] = {"status": ts, "body": tb, "rate_limit": _rate_info(th)}
                        return jsonify(result), ts
                else:
                    q_ex = ""
                    if exclude:
                        parts = [e.strip() for e in exclude.split(",") if e.strip()]
                        if parts:
                            q_ex = "".join(f" -is:{p}" for p in parts)
                    s_params = {
                        "query": f"from:{user['username']}{q_ex}",
                        "max_results": limit,
                        "tweet.fields": "created_at,public_metrics,lang,possibly_sensitive,entities,referenced_tweets,attachments,author_id",
                        "expansions": "author_id,attachments.media_keys",
                        "user.fields": "name,username,profile_image_url,verified,public_metrics",
                        "media.fields": "type,url,preview_image_url,width,height,alt_text",
                    }
                    if token:
                        s_params["pagination_token"] = token
                    s_url = f"{API_BASE}/tweets/search/recent"
                    ss, sb, sh = _cached_get(client, s_url, _auth_headers(), s_params)

                    if ss == 200:
                        block = _hydrate_tweets(sb)
                        last_block = block
                        rows.extend(_tweets_block_to_rows(block))
                        token = (block.get("meta") or {}).get("next_token")
                        if not token:
                            break
                    else:
                        if fmt == "csv" and rows:
                            return _rows_to_csv(CSV_TWEET_FIELDS, rows, f"user_{user.get('username')}_partial.csv")
                        result["tweets_fallback_error"] = {"status": ss, "body": sb, "rate_limit": _rate_info(sh)}
                        return jsonify(result), ss

            if fmt == "csv":
                return _rows_to_csv(CSV_TWEET_FIELDS, rows, f"user_{user.get('username')}_tweets.csv")

            if not use_search:
                result["tweets"] = last_block or {"data": [], "includes": {}, "meta": {}}
            else:
                result["tweets_fallback_search"] = last_block or {"data": [], "includes": {}, "meta": {}}
            return jsonify(result)

    except httpx.HTTPError as e:
        return jsonify({"error": "http_error", "detail": str(e)}), 502

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=PORT)
