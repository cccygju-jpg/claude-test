// Vercel 서버리스 함수: 투표·PIN·확정·부 시간·변경 기록을 Upstash Redis(Vercel Marketplace)에 저장합니다.
// 환경변수는 Vercel에서 Upstash Redis를 연결하면 자동으로 들어옵니다.
// (선택) GOLF_SALT 환경변수를 넣으면 PIN 해시가 더 안전해집니다.
const crypto = require("crypto");

const URL_ = process.env.KV_REST_API_URL || process.env.UPSTASH_REDIS_REST_URL;
const TOKEN = process.env.KV_REST_API_TOKEN || process.env.UPSTASH_REDIS_REST_TOKEN;
const SALT = process.env.GOLF_SALT || "golf-2026-10";

const KEY = "golf-votes-2026-10";      // hash: "날짜|이름" → {s,t},  "meta|confirmed", "meta|times"
const PINKEY = "golf-pins-2026-10";    // hash: 이름 → sha256(PIN)
const LOGKEY = "golf-log-2026-10";     // list: 최근 변경 기록
const PLAYERS = ["주영광", "오슬기", "박철희", "지현준"];
const DATE_RE = /^2026-10-(0[1-9]|[12]\d|3[01])$/;

async function redis(commands) {
  const r = await fetch(`${URL_}/pipeline`, {
    method: "POST",
    headers: { Authorization: `Bearer ${TOKEN}`, "Content-Type": "application/json" },
    body: JSON.stringify(commands),
  });
  if (!r.ok) throw new Error("redis " + r.status);
  return r.json();
}
const hashPin = (player, pin) =>
  crypto.createHash("sha256").update(`${player}:${pin}:${SALT}`).digest("hex");
const cleanS = (s) => [...new Set((Array.isArray(s) ? s : []).filter((x) => [1, 2, 3].includes(x)))].sort();
const logCmds = (entry) => [["LPUSH", LOGKEY, JSON.stringify({ ...entry, t: Date.now() })], ["LTRIM", LOGKEY, 0, 99]];

module.exports = async (req, res) => {
  res.setHeader("Cache-Control", "no-store");
  if (!URL_ || !TOKEN) return res.status(503).json({ error: "저장소(Upstash Redis)가 연결되지 않았습니다." });

  try {
    if (req.method === "GET") {
      const out = await redis([["HGETALL", KEY], ["HKEYS", PINKEY], ["LRANGE", LOGKEY, 0, 29]]);
      const flat = out[0].result || [];
      const votes = {}, meta = {};
      for (let i = 0; i < flat.length; i += 2) {
        const k = flat[i], v = JSON.parse(flat[i + 1]);
        if (k.startsWith("meta|")) meta[k.slice(5)] = v;
        else { const [date, player] = k.split("|"); (votes[date] = votes[date] || {})[player] = v; }
      }
      const log = (out[2].result || []).map((x) => { try { return JSON.parse(x); } catch (e) { return null; } }).filter(Boolean);
      return res.status(200).json({ votes, meta, pinSet: out[1].result || [], log });
    }

    if (req.method !== "POST") {
      res.setHeader("Allow", "GET, POST");
      return res.status(405).json({ error: "허용되지 않는 메서드" });
    }

    const b = typeof req.body === "string" ? JSON.parse(req.body) : req.body || {};
    const { action, player, pin } = b;
    if (!PLAYERS.includes(player) || !/^\d{4}$/.test(String(pin || "")))
      return res.status(400).json({ error: "이름 또는 PIN 형식이 잘못됐어요 (숫자 4자리)" });

    const [{ result: stored }] = await redis([["HGET", PINKEY, player]]);
    const h = hashPin(player, String(pin));

    // PIN 등록 / 확인
    if (action === "auth") {
      if (!stored) { await redis([["HSETNX", PINKEY, player, h]]); return res.status(200).json({ ok: true, created: true }); }
      if (stored !== h) return res.status(401).json({ error: "PIN이 맞지 않아요" });
      return res.status(200).json({ ok: true });
    }
    if (!stored || stored !== h) return res.status(401).json({ error: "PIN이 맞지 않아요" });

    if (action === "vote") {
      const entries = b.entries;
      if (!Array.isArray(entries) || entries.length > 40) return res.status(400).json({ error: "잘못된 요청" });
      const t = Date.now(), cmds = [];
      for (const e of entries) {
        if (!DATE_RE.test(e.date)) return res.status(400).json({ error: "잘못된 날짜" });
        cmds.push(["HSET", KEY, `${e.date}|${player}`, JSON.stringify({ s: cleanS(e.s), t })]);
      }
      if (entries.length === 1) cmds.push(...logCmds({ k: "vote", p: player, d: entries[0].date, s: cleanS(entries[0].s) }));
      else if (entries.length > 1) cmds.push(...logCmds({ k: "bulk", p: player, n: entries.length }));
      if (cmds.length) await redis(cmds);
      return res.status(200).json({ ok: true });
    }

    if (action === "confirm") {
      const { date } = b, s = Number(b.s);
      if (date === null) {
        await redis([["HDEL", KEY, "meta|confirmed"], ...logCmds({ k: "unconfirm", p: player })]);
      } else {
        if (!DATE_RE.test(date) || ![1, 2, 3].includes(s)) return res.status(400).json({ error: "잘못된 요청" });
        await redis([["HSET", KEY, "meta|confirmed", JSON.stringify({ date, s, by: player })], ...logCmds({ k: "confirm", p: player, d: date, s: [s] })]);
      }
      return res.status(200).json({ ok: true });
    }

    if (action === "times") {
      const times = {};
      for (const n of [1, 2, 3]) times[n] = String((b.times || {})[n] || "").slice(0, 20);
      await redis([["HSET", KEY, "meta|times", JSON.stringify(times)], ...logCmds({ k: "times", p: player })]);
      return res.status(200).json({ ok: true });
    }

    return res.status(400).json({ error: "알 수 없는 요청" });
  } catch (e) {
    return res.status(500).json({ error: "서버 오류" });
  }
};
