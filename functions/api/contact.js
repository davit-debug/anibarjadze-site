/**
 * Cloudflare Pages Function — POST /api/contact
 *
 * საკონტაქტო ფორმის მიღება და ელფოსტით გადაგზავნა Resend-ის API-ით.
 * გარემოს ცვლადები (Cloudflare Pages → Settings → Environment variables):
 *   RESEND_API_KEY  — Resend-ის API გასაღები (Secret)
 *   CONTACT_TO      — მიმღები(ები), მძიმით გამოყოფილი
 *   CONTACT_FROM    — გამგზავნი Resend-ში დადასტურებული დომენიდან, მაგ. „საიტი <forma@anibarjadze.ge>“
 *
 * პრინციპები: პერსონალური მონაცემები ლოგში არ იწერება; ჯანმრთელობის თავისუფალი ველი არ არსებობს;
 * honeypot („website“) ჩუმად აბრუნებს წარმატებას; ნებისმიერი ველი > 500 სიმბოლო უარყოფილია.
 *
 * „routing“ (არასავალდებულო; მხოლოდ იმ საიტზე, რომლის site.config.json-შიც ROUTING_OPTIONS არის — საიტი 4):
 * მიიღება მხოლოდ ROUTING_LABELS-ის გასაღები (≤ 100 სიმბოლო); უცნობი მნიშვნელობა იგნორირდება. build.py ამოწმებს,
 * რომ კონფიგის ROUTING_OPTIONS აქ იგივე ტექსტით არის. კოლეგები ამ ფორმით არ აგზავნიან განაცხადს — მხოლოდ ელფოსტით.
 */

const MAX_FIELD = 500;
const MAX_BODY = 16 * 1024;
const MAX_FIELDS = 20;

const MSG = {
  method: "ეს მისამართი მხოლოდ ფორმის გაგზავნას იღებს.",
  origin: "მოთხოვნა უარყოფილია.",
  tooLarge: "მოთხოვნა ძალიან დიდია.",
  badRequest: "ფორმის წაკითხვა ვერ მოხერხდა. სცადეთ თავიდან.",
  tooLong: "ერთ-ერთი ველი ძალიან გრძელია (მაქსიმუმ 500 სიმბოლო).",
  name: "გთხოვთ, მიუთითოთ სახელი.",
  contact: "გთხოვთ, მიუთითოთ ტელეფონი ან ელფოსტა.",
  contactInvalid: "ტელეფონი ან ელფოსტა არასწორი ფორმატითაა.",
  consent: "გაგზავნისთვის საჭიროა თანხმობა მონაცემების დამუშავებაზე.",
  config: "ფორმა დროებით ვერ მუშაობს. მომწერეთ WhatsApp-ზე ან Messenger-ით.",
  send: "შეტყობინება ვერ გაიგზავნა. სცადეთ თავიდან ან მომწერეთ WhatsApp-ზე.",
  ok: "გმადლობთ! შეტყობინება მიღებულია — გიპასუხებთ 24 საათში.",
};

const FORMAT_LABELS = { kabineti: "კაბინეტში", onlain: "ონლაინ" };
const MAX_ROUTING = 100;
// დაშვებული „routing“ მნიშვნელობები → ტექსტი წერილში (ემთხვევა sites/4-centri/site.config.json-ის ROUTING_OPTIONS-ს)
const ROUTING_LABELS = {
  "ani": "ანი ბარჯაძე — ინდივიდუალური ფსიქოთერაპია",
  "ar-vici": "ჯერ არ ვიცი — დამეხმარეთ არჩევაში",
  "molodini-tsqvilebi": "მოლოდინის სია: წყვილების ფსიქოთერაპია",
  "molodini-bavshvebi": "მოლოდინის სია: ბავშვთა და მოზარდთა",
  "molodini-jgufi": "მოლოდინის სია: ჯგუფი",
  "kompania": "კომპანიის სახელით (HR)",
};
const EMAIL_RE = /^[^\s@<>]+@[^\s@<>]+\.[^\s@<>]{2,}$/;
const PHONE_RE = /^[+()\-\s\d]{6,25}$/;

export async function onRequestPost(context) {
  const { request, env } = context;

  const origin = request.headers.get("Origin");
  if (origin) {
    let sameHost = false;
    try { sameHost = new URL(origin).host === new URL(request.url).host; } catch (_) { /* invalid origin */ }
    if (!sameHost) return reply(request, 403, { ok: false, error: MSG.origin });
  }

  const length = Number(request.headers.get("Content-Length") || 0);
  if (length > MAX_BODY) return reply(request, 413, { ok: false, error: MSG.tooLarge });

  let raw;
  try {
    raw = await readFields(request);
  } catch (_) {
    return reply(request, 400, { ok: false, error: MSG.badRequest });
  }
  if (!raw) return reply(request, 400, { ok: false, error: MSG.badRequest });

  const entries = Object.entries(raw);
  if (entries.length > MAX_FIELDS) return reply(request, 400, { ok: false, error: MSG.badRequest });
  for (const [, value] of entries) {
    if (typeof value === "string" && value.length > MAX_FIELD) {
      return reply(request, 400, { ok: false, error: MSG.tooLong });
    }
  }

  // honeypot: ბოტს ვეუბნებით, რომ ყველაფერი რიგზეა, და არაფერს ვაგზავნით
  if (clean(raw.website)) return reply(request, 200, { ok: true, message: MSG.ok });

  const name = clean(raw.name);
  const contact = clean(raw.contact);
  const time = clean(raw.time);
  const format = FORMAT_LABELS[clean(raw.format)] || "არ არის მითითებული";
  const consent = ["yes", "on", "true", "1"].includes(String(raw.consent ?? "").toLowerCase());
  const channel = /^[a-z0-9_-]{1,40}$/.test(clean(raw.channel)) ? clean(raw.channel) : "site_form";
  const page = /^\/[a-z0-9\-/._]{0,120}$/i.test(clean(raw.page)) ? clean(raw.page) : "—";
  const routingKey = clean(raw.routing);
  const routing = routingKey.length <= MAX_ROUTING && Object.prototype.hasOwnProperty.call(ROUTING_LABELS, routingKey)
    ? routingKey : "";

  if (!name) return reply(request, 422, { ok: false, error: MSG.name });
  if (!contact) return reply(request, 422, { ok: false, error: MSG.contact });
  const isEmail = EMAIL_RE.test(contact);
  if (!isEmail && !(PHONE_RE.test(contact) && contact.replace(/\D/g, "").length >= 6)) {
    return reply(request, 422, { ok: false, error: MSG.contactInvalid });
  }
  if (!consent) return reply(request, 422, { ok: false, error: MSG.consent });

  if (!env.RESEND_API_KEY || !env.CONTACT_TO || !env.CONTACT_FROM) {
    console.error("contact: missing env configuration");
    return reply(request, 500, { ok: false, error: MSG.config });
  }

  const now = new Date();
  const stamp = tbilisiTime(now);
  const text = [
    "ახალი მიმართვა საიტიდან",
    "",
    `სახელი: ${name}`,
    `კონტაქტი: ${contact}`,
    `სასურველი დრო: ${time || "არ არის მითითებული"}`,
    `ფორმატი: ${format}`,
    ...(routing ? [`ვისთან: ${ROUTING_LABELS[routing]}`] : []),
    "თანხმობა მონაცემების დამუშავებაზე: დიახ",
    "",
    `გვერდი: ${page}`,
    `არხი: ${channel}`,
    `დრო: ${stamp} (თბილისი) · ${now.toISOString()}`,
  ].join("\n");

  const payload = {
    from: env.CONTACT_FROM,
    to: env.CONTACT_TO.split(",").map((s) => s.trim()).filter(Boolean),
    subject: `[${channel}] ახალი მიმართვა საიტიდან — ${stamp}`,
    text,
    tags: [{ name: "channel", value: channel }, ...(routing ? [{ name: "routing", value: routing }] : [])],
  };
  if (isEmail) payload.reply_to = contact;

  try {
    const res = await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.RESEND_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      console.error("contact: resend status", res.status);
      return reply(request, 502, { ok: false, error: MSG.send });
    }
  } catch (_) {
    console.error("contact: resend unreachable");
    return reply(request, 502, { ok: false, error: MSG.send });
  }

  return reply(request, 200, { ok: true, message: MSG.ok });
}

export async function onRequest(context) {
  return new Response(JSON.stringify({ ok: false, error: MSG.method }), {
    status: 405,
    headers: { Allow: "POST", "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
  });
}

async function readFields(request) {
  const type = (request.headers.get("Content-Type") || "").toLowerCase();
  if (type.includes("application/json")) {
    const data = await request.json();
    if (!data || typeof data !== "object" || Array.isArray(data)) return null;
    const out = {};
    for (const [k, v] of Object.entries(data)) {
      if (typeof v === "string" || typeof v === "boolean" || typeof v === "number") out[k] = String(v);
      else return null;
    }
    return out;
  }
  if (type.includes("multipart/form-data") || type.includes("application/x-www-form-urlencoded")) {
    const form = await request.formData();
    const out = {};
    for (const [k, v] of form.entries()) {
      if (typeof v !== "string") return null; // ფაილები არ მიიღება
      out[k] = v;
    }
    return out;
  }
  return null;
}

function clean(value) {
  return String(value ?? "").replace(/[\u0000-\u001F\u007F]+/g, " ").replace(/\s+/g, " ").trim();
}

// საქართველო UTC+4-ზეა, ზაფხულის დროის გარეშე
function tbilisiTime(date) {
  return new Date(date.getTime() + 4 * 3600 * 1000).toISOString().slice(0, 16).replace("T", " ");
}

function wantsJson(request) {
  return (request.headers.get("Accept") || "").includes("application/json");
}

function reply(request, status, body) {
  if (wantsJson(request)) {
    return new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
    });
  }
  // JS-ის გარეშე გაგზავნილი ფორმა: მარტივი ქართული გვერდი
  const message = body.ok ? MSG.ok : body.error;
  const page = `<!doctype html><html lang="ka"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex">
<title>${body.ok ? "შეტყობინება მიღებულია" : "შეტყობინება ვერ გაიგზავნა"}</title>
<link rel="stylesheet" href="/assets/css/style.css"></head>
<body><main id="main" class="container section"><h1>${body.ok ? "გმადლობთ!" : "ვერ გაიგზავნა"}</h1>
<p>${escapeHtml(message)}</p><p><a class="btn btn-secondary" href="/kontaqti/">დაბრუნება კონტაქტის გვერდზე</a></p></main></body></html>`;
  return new Response(page, {
    status,
    headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" },
  });
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
