# anibarjadze.ge — ანი ბარჯაძის საიტი (სამი ვარიანტი)

სტატიკური, მხოლოდ ქართულენოვანი საიტი. რეპოზიტორიაში სამი ალტერნატიული ვარიანტია — ანი ერთს აირჩევს, ის გავა anibarjadze.ge-ზე. აგება — `python3`-ის სტანდარტული ბიბლიოთეკით, დამოკიდებულებების გარეშე (`npm` არ გამოიყენება).

| ვარიანტი | საქაღალდე | იდეა |
|---|---|---|
| 1 · პირადი ბრენდი | `sites/1-brendi` | ერთი ადამიანი, ერთი ფასი, ერთი შეტყობინების მანძილი |
| 2 · ბიბლიოთეკა | `sites/2-biblioteka` | ქართულენოვანი ბიბლიოთეკა ფსიქოთერაპიაზე — ავტორიანი, წყაროებიანი გვერდები |
| 3 · სხეული | `sites/3-sxeuli` | ფსიქოთერაპია, რომელიც სიტყვასთან ერთად სხეულსაც უსმენს |

**დემო (სამივე ერთად):** https://davit-debug.github.io/anibarjadze-site/ — ყველა გვერდი noindex-ია, `robots.txt` = `Disallow: /`, ზედა დემო-ზოლით ვარიანტებს შორის გადახვალთ, ფორმა არ იგზავნება. იდება ავტომატურად `main`-ზე push-ისას (`.github/workflows/pages.yml`).

სპეციფიკაციები: `claudedocs/specs/` (`_common.md` — საერთო წესები და დადასტურებული ფაქტები), საწყისი კონცეფცია: `claudedocs/ani-barjadze-saiti-koncefcia.md`.

## სტრუქტურა

| გზა | რა არის |
|---|---|
| `sites/<slug>/site.config.json` | საიტის ყველა `{{TOKEN}}`-ის წყარო (სახელი, მისამართი, ტელეფონი, ფასი, საათები, ბმულები, `THEME_COLOR`, `AUTHOR_PATH`) + საიტის სიები: `PLANNED_PATHS`, `NAV_GROUPS`, `ALLOWED_THERAPY_COMPOUNDS`, `SAUKETESO_ALLOWED` |
| `sites/<slug>/src/pages/**/*.html` | გვერდები: `<!--meta {…} -->` ბლოკი + `<main>`-ის შიგთავსი |
| `sites/<slug>/src/partials/*.html` | ჰედერი, ფუტერი, CTA, ავტორის ბარათი, ფორმა, დისკლეიმერი, უსაფრთხოების ბლოკი |
| `sites/<slug>/src/layout.html` | საერთო ჩარჩო (`<head>`, მეტა-ტეგები, JSON-LD) |
| `sites/<slug>/assets/` | CSS, JS, სურათები → `<out>/assets/` |
| `shared/fonts/*.woff2`, `shared/fonts.css` | თვითჰოსტირებული Noto Sans Georgian (400/700) და Noto Serif Georgian (400/500/700) — ყველა საიტისთვის საერთო; `{{FONTS_CSS}}` ტოკენით ჩაისმება `<head>`-ში, ფაილები → `<out>/assets/fonts/` |
| `demo/index.html`, `demo/404.html` | დემოს ვარიანტების არჩევის გვერდი და GitHub Pages-ის 404 (`--all`) |
| `demo/palettes.json`, `demo/ferebi.html` | დემოს ფერთა პალიტრები (ზოლში „ფერები“, `?ferebi=<id>`, არჩევანი `localStorage`-ში) და ფერების შედარების გვერდი `<out>/ferebi/` (`--all --demo`) |
| `functions/api/contact.js` | Cloudflare Pages Function ფორმისთვის (Resend) |
| `build.py` | აგება + ვალიდაცია (ერთი სკრიპტი სამივე საიტისთვის) |

## აგება და ნახვა

```bash
python3 build.py                                          # sites/1-brendi → dist/
python3 build.py --site sites/2-biblioteka                # სხვა საიტი → dist/
python3 build.py --site sites/2-biblioteka --page src/pages/fasi.html   # ერთი გვერდი (გზა საიტის საქაღალდიდან ან cwd-დან)
python3 build.py --site sites/3-sxeuli --release          # გაშვებამდე: ყველა [ფრჩხილი] და დაუწერელი გვერდი = შეცდომა
python3 build.py --placeholders-report claudedocs/placeholders-table.md  # [ფრჩხილების] ცხრილი: ადგილი · კონფიგი · ფაილები · რაოდენობა
python3 -m http.server -d dist 8080                       # ნახვა: http://localhost:8080
```

დემო ლოკალურად (სამივე საიტი, ისევე როგორც GitHub Pages-ზე):

```bash
python3 build.py --all --demo --site-url http://localhost:8080 --out dist
python3 -m http.server -d dist 8080                       # http://localhost:8080/ — ვარიანტების არჩევა
```

| პარამეტრი | რას აკეთებს |
|---|---|
| `--site sites/<slug>` | რომელი საიტი აიგოს (ნაგულისხმევი: `sites/1-brendi`) |
| `--out <dir>` | სად ჩაიწეროს (ნაგულისხმევი: `dist/`). რეპოზიტორიის შიგნით ძველი შიგთავსი ჯერ იშლება; გარეთ — არა. `sites/`, `shared/` და სხვა წყაროს საქაღალდეებში ჩაწერა აკრძალულია |
| `--site-url <url>` | `SITE_URL`-ის ჩანაცვლება. თუ URL-ს გზა აქვს (`https://x.github.io/repo/1-brendi`), ყველა „/…“ ბმული, `src`, `action`, CSS-ის `url(/…)` ამ გზით იწყება. ვალიდაცია გზის გარეშე ტარდება |
| `--demo` | ყველა გვერდზე `noindex, nofollow`, canonical არ არის, `robots.txt` = `Disallow: /`, `sitemap.xml` და `llms.txt` არ იწერება, ზედა დემო-ზოლი (ვარიანტებს შორის + ფერების არჩევა `demo/palettes.json`-იდან; `?ferebi=<id>` ირჩევს — ზოლიდან შეცვლისას URL-ის `?ferebi`-იც განახლდება, `localStorage`-ის გარეშე კი ფერი შიდა ბმულებით გადადის; `?embed=1` ზოლს მალავს და არჩევანს არ ინახავს), ფორმაზე `data-demo="1"` — `main.js` აჩვენებს „დემო-რეჟიმში ფორმა არ იგზავნება“ |
| `--all` | ყველა `sites/*/` → `<out>/<slug>/` (`SITE_URL` = `<site-url>/<slug>`) + `<out>/index.html` (არჩევა) და `<out>/404.html`. ჯერ არარსებული საიტი გამოტოვდება (WARN) |

build ბეჭდავს ERROR / WARN / INFO სიას გვერდების მიხედვით; ERROR-ის შემთხვევაში გამოსვლის კოდი 1-ია. ამოწმებს: სათაური/description-ის სიგრძე და უნიკალურობა, ერთი H1 = meta.h1, JSON-LD, შიდა ბმულები და `#ანკორები`, `<img>` alt/width/height, „თერაპევტი/თერაპია“ ცალკე სიტყვად (სათაური, H1, ნავიგაცია, ანკორები, schema; დასაშვები შესიტყვებები — `ALLOWED_THERAPY_COMPOUNDS`), `/en/` და hreflang, აკრძალული სიტყვები. `noindex` გვერდზე (404) canonical არ იწერება და JSON-LD მინიმალურია. ფორმა ლოკალურ სერვერზე არ მუშაობს (Pages Function-ს Cloudflare სჭირდება).

ბლოგის ბარათები ხელით აღარ იწერება: `{{BLOG_CARDS}}` ტოკენი `/blogi/`-ის ყველა `type: Article` გვერდიდან აგებს ბარათს (თემა = meta `kicker`, რეზიუმე = meta `card_summary` ან description, თარიღი, წაკითხვის დრო = `.prose`-ის სიტყვები ÷ 180, ავტორი → `AUTHOR_PATH`). `{{PAGE_READING_MIN}}` ნებისმიერ გვერდზე მუშაობს.

## ფრჩხილებიანი ადგილების შევსება

კვადრატულ ფრჩხილებში ჩაწერილი ყველა მნიშვნელობა (`[ფასი]`, `[უნივერსიტეტი]`, `[სამუშაო საათები]`…) განზრახ დატოვებული ადგილია — **ივსება მხოლოდ დოკუმენტით ან ანის პასუხით, არაფერი გამოიგონება**.

1. საერთო მნიშვნელობები — არჩეული საიტის `site.config.json`-ში: `PRICE` (მაგ. `120 ₾`), `PRICE_VALUE` (მხოლოდ რიცხვი, მაგ. `120` — schema-ს Offer-ისთვის), `HOURS`, `OPENING_HOURS_SPEC` (schema), `PHONE_DISPLAY`, `PHONE_TEL`, `WA_URL` (იგივე ნომერი, build ამოწმებს), `GBP_REVIEW_URL`, `AUTHOR_CREDENTIAL`, `SAME_AS` (tsamali, yell… პროფილები), ფოტოების გზები.
2. გვერდებზე დარჩენილი ფრჩხილები — `python3 build.py --site sites/<slug>` თითო გვერდზე INFO ხაზად ჩამოთვლის; სრული ცხრილი — `--placeholders-report <ფაილი.md>`.
3. გაშვებამდე `python3 build.py --site sites/<slug> --release` უნდა დასრულდეს შეცდომის გარეშე.

**შენიშვნა ელფოსტაზე:** `EMAIL` = `ani@anibarjadze.ge` (ციფრებიანი Gmail საიტზე არ ქვეყნდება). მისამართი გაშვებამდე უნდა ამუშავდეს: Cloudflare Email Routing → ანის Gmail.

შესავსები ადგილების აღწერა (რა გვჭირდება ანისგან, პრიორიტეტი), ასეტები და გაშვების ნაბიჯები: `claudedocs/placeholders.md`.

## გაშვება Cloudflare Pages-ზე (არჩეული საიტი)

- **Build command:** `python3 build.py --site sites/<slug> --out dist` (მაგ. `sites/1-brendi`)
- **Build output directory:** `dist`
- **Root directory:** რეპოზიტორიის ფესვი (`functions/` აქედან იკითხება — `dist`-ში არ კოპირდება)
- `--demo` და `--site-url` აქ **არ** გამოიყენება: `SITE_URL` კონფიგიდან მოდის (`https://anibarjadze.ge`).
- **გარემოს ცვლადები (Production + Preview):**
  - `RESEND_API_KEY` — Resend-ის გასაღები (Secret)
  - `CONTACT_TO` — სად მივიდეს ფორმა (მაგ. ანის ელფოსტა)
  - `CONTACT_FROM` — გამგზავნი Resend-ში დადასტურებული დომენიდან, მაგ. `საიტი <forma@anibarjadze.ge>`
- build ავტომატურად წერს `sitemap.xml` (მხოლოდ ინდექსირებადი გვერდები), `robots.txt` (Googlebot და AI-ბოტები დაშვებულია — გადაწყვეტილება კომენტარშია), `llms.txt`, `feed.xml` (ბლოგის RSS), `_headers` (უსაფრთხოება, CSP — ჩაშენებული შრიფტების `<style>`-ის sha256 ავტომატურად ემატება `style-src`-ს; ასეტებისა და შრიფტების ქეში), `_redirects` (ცარიელი, მაგალითით).
- ანალიტიკა: Plausible-ის `<script>` ჩასვით `ANALYTICS_SNIPPET`-ში. ივენთები (`cta_whatsapp`, `cta_messenger`, `cta_phone`, `form_submit`, `review_link`) უკვე მიბმულია. სხვა სერვისის შემთხვევაში განაახლეთ `CSP`.

## GitHub Pages (დემო)

`.github/workflows/pages.yml` `main`-ზე push-ისას (ან ხელით, „Run workflow“) უშვებს `python3 build.py --all --demo --site-url https://davit-debug.github.io/anibarjadze-site --out dist` და `dist/`-ს Pages-ზე დებს. რეპოზიტორიის პარამეტრებში: **Settings → Pages → Source: GitHub Actions**.

## რა აკლია (გაშვებამდე)

- **ფოტოები:** პორტრეტი (hero, 4:5), კაბინეტი, შესასვლელი — ახლა `assets/img/placeholder-*.svg`; ჩაანაცვლეთ `PHOTO_*` ტოკენებით (AVIF/WebP, ≤120 KB hero).
- **OG სურათი:** `assets/img/og-default.png` დროებითია. საჭიროა 1200×630 PNG/JPG პორტრეტით; გვერდზე ცალკე სურათისთვის — meta `og_image`.
- **ტელეფონი და WhatsApp-ის ნომერი** (სამუშაო SIM), **ფასი**, **სამუშაო საათები**.
- **კვალიფიკაცია:** ხარისხი, უნივერსიტეტი, გეშტალტის ინსტიტუტი და საფეხური, სხეულზე ორიენტირებული პროგრამა და საათები, ასოციაციის წევრობა — დოკუმენტებით.
- **Google-ის შეფასების ბმული** (GBP-ის შექმნის შემდეგ), სტატიკური რუკის სურათი, ვიდეო-კლიპი (სურვილისამებრ).
