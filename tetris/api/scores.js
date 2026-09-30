// Vercel 서버리스 함수: 난이도별 전체 랭킹을 Upstash Redis(Vercel Marketplace)에 저장합니다.
// 환경변수(KV_REST_API_URL / KV_REST_API_TOKEN)는 Vercel에서 Upstash Redis를 프로젝트에 연결하면 자동으로 들어옵니다.
const crypto = require("crypto");

const URL_ = process.env.KV_REST_API_URL || process.env.UPSTASH_REDIS_REST_URL;
const TOKEN = process.env.KV_REST_API_TOKEN || process.env.UPSTASH_REDIS_REST_TOKEN;

const DIFFS = ["easy", "normal", "hard"];
const KEEP = 100;      // 난이도별 최대 보관 개수
const SHOW = 10;       // 화면에 내려주는 개수
const MAX_SCORE = 3000000, MAX_LINES = 1500;
const COOLDOWN_SEC = 10; // 같은 IP의 연속 등록 간격

const key = (d) => `tetris:top:${d}`;

async function redis(commands) {
  const r = await fetch(`${URL_}/pipeline`, {
    method: "POST",
    headers: { Authorization: `Bearer ${TOKEN}`, "Content-Type": "application/json" },
    body: JSON.stringify(commands),
  });
  if (!r.ok) throw new Error("redis " + r.status);
  return r.json();
}
const cleanName = (s) =>
  String(s || "").replace(/[\u0000-\u001f\u007f<>]/g, "").replace(/\s+/g, " ").trim().slice(0, 10);

module.exports = async (req, res) => {
  res.setHeader("Cache-Control", "no-store");
  if (!URL_ || !TOKEN) return res.status(503).json({ error: "저장소(Upstash Redis)가 연결되지 않았습니다." });

  try {
    if (req.method === "GET") {
      const d = String((req.query && req.query.d) || "");
      if (!DIFFS.includes(d)) return res.status(400).json({ error: "난이도가 잘못됐어요" });
      const [{ result }] = await redis([["ZREVRANGE", key(d), 0, SHOW - 1]]);
      const scores = (result || []).map((m) => {
        try { const o = JSON.parse(m); return { id: o.i, name: o.n, score: o.s, lines: o.l, level: o.v, t: o.t }; }
        catch (e) { return null; }
      }).filter(Boolean);
      return res.status(200).json({ scores });
    }

    if (req.method !== "POST") {
      res.setHeader("Allow", "GET, POST");
      return res.status(405).json({ error: "허용되지 않는 메서드" });
    }

    const b = typeof req.body === "string" ? JSON.parse(req.body) : req.body || {};
    const name = cleanName(b.name);
    const score = Number(b.score), lines = Number(b.lines), level = Number(b.level);
    if (!DIFFS.includes(b.diff)) return res.status(400).json({ error: "난이도가 잘못됐어요" });
    if (!name) return res.status(400).json({ error: "닉네임을 입력해 주세요" });
    if (!Number.isInteger(score) || score < 1 || score > MAX_SCORE ||
        !Number.isInteger(lines) || lines < 0 || lines > MAX_LINES ||
        !Number.isInteger(level) || level < 1 || level > 200)
      return res.status(400).json({ error: "기록 값이 올바르지 않아요" });

    // IP당 연속 등록 제한 (IP 원문은 해시로만 저장)
    const ip = String(req.headers["x-forwarded-for"] || "").split(",")[0].trim() || "unknown";
    const ipKey = "tetris:rl:" + crypto.createHash("sha256").update(ip).digest("hex").slice(0, 24);
    const [{ result: lock }] = await redis([["SET", ipKey, "1", "NX", "EX", COOLDOWN_SEC]]);
    if (!lock) return res.status(429).json({ error: `잠시 후 다시 시도해 주세요 (${COOLDOWN_SEC}초 간격)` });

    const id = crypto.randomBytes(6).toString("hex");
    const member = JSON.stringify({ i: id, n: name, s: score, l: lines, v: level, t: Date.now() });
    const out = await redis([
      ["ZADD", key(b.diff), score, member],
      ["ZREMRANGEBYRANK", key(b.diff), 0, -(KEEP + 1)],
      ["ZREVRANK", key(b.diff), member],
    ]);
    const rank = out[2].result; // 0부터 시작, 100위 밖이면 null
    return res.status(200).json({ id, rank: rank === null ? null : rank + 1 });
  } catch (e) {
    return res.status(500).json({ error: "서버 오류가 발생했어요" });
  }
};
