#!/usr/bin/env python3
"""anibarjadze.ge — სტატიკური საიტის აგება და ვალიდაცია (მხოლოდ python3 stdlib).

გამოყენება:
    python3 build.py                         # სრული აგება (sites/1-brendi → dist/): sitemap, robots, llms.txt, _headers, _redirects
    python3 build.py --page src/pages/X.html # ერთი გვერდის აგება და შემოწმება (გზა cwd-დან ან საიტის საქაღალდიდან)
    python3 build.py --release               # გაშვებამდე: ფრჩხილებიანი ადგილები და დაუწერელი გვერდები = შეცდომა
    python3 build.py --placeholders-report claudedocs/placeholders-table.md   # [ფრჩხილების] ცხრილი ფაილებით

გვერდის ფორმატი (<საიტი>/src/pages/**/*.html):
    <!--meta { ...JSON... } -->
    ...<main>-ის შიგთავსი...

სინტაქსი გვერდებსა და partial-ებში:
    {{KEY}}                    site.config.json-ის მნიშვნელობა ან გვერდის ტოკენი (PAGE_*, YEAR, TEL_URL)
    {{> name}}                 src/partials/name.html
    {{> name key="value"}}     partial არგუმენტებით; partial-ში {{@key}} ან {{@key|ნაგულისხმევი}}
    {{asset:/assets/x.css}}    ასეტის URL ქეშის ვერსიით (?v=hash)
    {{nav:key}} / {{navgroup:key}}  ნავიგაციის აქტიური მდგომარეობა (header partial-ში)
    {{BLOG_CARDS}}             ბლოგის ბარათები (<ul class="cards">) ყველა სტატიიდან, ახლიდან ძველისკენ
    {{PAGE_READING_MIN}}       გვერდის .prose ტექსტის წაკითხვის დრო წუთებში (სიტყვები ÷ 180)
    {{FONTS_CSS}}              shared/fonts.css-ის @font-face წესები <style>-ში (თვითჰოსტირებული შრიფტები)
    {{PAGE_STATUS}}            გვერდის meta.status: live (ნაგულისხმევი) ან planned
    {{ROUTING_FIELD}}          ფორმის <select name="routing"> კონფიგის ROUTING_OPTIONS-იდან (მის გარეშე — ცარიელი)

გვერდის სტატუსი (meta "status": "live" | "planned"; საიტი 4 — „დაგეგმილია — ადგილი ღიაა“):
    planned გვერდს სჭირდება {{> status-planned}}, H2 „ვინ ატარებს“ და „რა შეგვიძლია დღეს“, უსაფრთხოების ბლოკი;
    SERVICES-ში არ უნდა იყოს და Service/Offer კვანძს არ იღებს. თუ .prose-ში < 1 000 სიტყვაა — ავტომატურად
    noindex (sitemap/llms.txt/feed-ის გარეშე), INFO ხაზით.

ორგანიზაცია (მხოლოდ თუ კონფიგში ORG_LEGAL_NAME არის): JSON-LD-ში practice = ["Organization","MedicalBusiness"],
    name = SITE_NAME, legalName/taxID/foundingDate მხოლოდ შევსებული მნიშვნელობით, member = ORG_MEMBERS (მხოლოდ
    რეალური პიროვნებები: PERSON_ID ან PEOPLE), SERVICES[].provider → Person. FORBIDDEN_UNTIL_TEAM — სიტყვები,
    რომლებიც ERROR-ია, სანამ ORG_MEMBERS-ში < 2 ადამიანია; კონფიდენციალურობის აბსოლუტური ფორმები — ყოველთვის.

მრავალსაიტიანი რეჟიმი:
    საიტი = sites/<slug>/ საქაღალდე: src/ (pages, partials, layout.html), assets/, site.config.json.
    საიტზე დამოკიდებული სიები (PLANNED_PATHS, NAV_GROUPS, ALLOWED_THERAPY_COMPOUNDS, SAUKETESO_ALLOWED)
    site.config.json-შია; შრიფტები საერთოა (shared/fonts → <out>/assets/fonts/).
    python3 build.py --site sites/2-biblioteka                  # სხვა საიტი → dist/
    python3 build.py --site sites/<slug> --out dist/<slug>      # სხვა გამოსატანი საქაღალდე
    python3 build.py --site-url https://example.org/sub         # SITE_URL-ის ჩანაცვლება; path (/sub) = ბაზის გზა,
                                                                #   რომელიც ჩაწერისას ყველა „/…“ ბმულს წინ ემატება
    python3 build.py --demo                                     # დემო: noindex, canonical-ის გარეშე, Disallow: /,
                                                                #   sitemap/llms.txt-ის გარეშე, დემო-ზოლი, ფორმა არ იგზავნება
    python3 build.py --all --demo --site-url BASE --out dist    # ყველა sites/*/ → dist/<slug>/ + dist/index.html (არჩევა)
                                                                #   + dist/404.html (GitHub Pages)
                                                                #   + dist/ferebi/ (ფერების შედარება, demo/palettes.json)
    ვალიდაცია ყოველთვის ბაზის გზის გარეშე HTML-ზე ტარდება; ბაზა და დემო-ზოლი ემატება მხოლოდ ჩაწერისას.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import posixpath
import re
import shutil
import sys
from collections import Counter
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent
SITES_DIR = ROOT / "sites"
DEFAULT_SITE = SITES_DIR / "1-brendi"
SHARED_DIR = ROOT / "shared"
SHARED_FONTS_DIR = SHARED_DIR / "fonts"
FONTS_CSS_FILE = SHARED_DIR / "fonts.css"
DEMO_DIR = ROOT / "demo"

# საიტზე დამოკიდებული გზები — use_site()-ში ხელახლა ივსება (--site / --all); ფუნქციები მათ გამოძახებისას კითხულობენ.
SITE_DIR = DEFAULT_SITE
SRC = SITE_DIR / "src"
PAGES_DIR = SRC / "pages"
PARTIALS_DIR = SRC / "partials"
LAYOUT_FILE = SRC / "layout.html"
ASSETS_DIR = SITE_DIR / "assets"
CONFIG_FILE = SITE_DIR / "site.config.json"
DIST = ROOT / "dist"          # --out
BASE_PATH = ""                # --site-url-ის path ნაწილი (მაგ. /1-brendi); ცარიელი = საიტი დომენის ფესვშია

# საიტის კონფიგიდან (apply_site_config): ყველა დაგეგმილი გვერდი. ბმული ამ მისამართზე მიიღება, სანამ გვერდი
# ჯერ დაწერილი არ არის (სრულ აგებაზე WARN, --page რეჟიმში INFO, --release-ზე ERROR).
PLANNED_PATHS: list[str] = []
KNOWN_ENDPOINTS = {"/api/contact", "/sitemap.xml", "/robots.txt", "/llms.txt", "/feed.xml"}

# სტატიების სია (type: Article) — ივსება build_site()-ში; /blogi/-ის CollectionPage-ის, RSS-ისა და {{BLOG_CARDS}}-ისთვის.
ARTICLES: list = []

PAGE_TYPES = {"WebPage", "MedicalWebPage", "AboutPage", "ContactPage", "CollectionPage", "Article", "FAQPage"}

# ნავიგაციის ჯგუფები (header partial-ში {{navgroup:KEY}}): ჯგუფი აქტიურია, თუ nav_key მის სიაშია.
# კონფიგში: "NAV_GROUPS": {"metodebi": ["fsiqoterapia", …]} ან {"metodebi": {"label": "მეთოდები", "keys": […]}}.
NAV_GROUPS: dict[str, list[str]] = {}
NAV_GROUP_LABELS: dict[str, str] = {}

# „საუკეთესო“ დასაშვებია მხოლოდ გზამკვლევში (კითხვით H2-ში და უარყოფით კონტექსტში). კონფიგი: SAUKETESO_ALLOWED.
DEFAULT_SAUKETESO_ALLOWED = ["/rogor-avirchiot-fsiqologi/"]
SAUKETESO_ALLOWED: set[str] = set()

# „თერაპია/თერაპევტი“ ცალკე სიტყვად დასაშვებია მხოლოდ ამ შესიტყვებებში (ბრუნვის დაბოლოებით: „გეშტალტ თერაპიის“ და ა.შ.).
# კონფიგი: ALLOWED_THERAPY_COMPOUNDS. ერთსიტყვიანი ფორმები (ფსიქოთერაპია, გეშტალტთერაპია) ისედაც არ ითვლება ცალკე სიტყვად.
DEFAULT_ALLOWED_THERAPY_COMPOUNDS = [
    "გეშტალტ თერაპია", "გეშტალტ თერაპევტი", "გეშტალტ-თერაპია", "გეშტალტ-თერაპევტი",
    "ორიენტირებული თერაპია", "ორიენტირებული თერაპევტი",
    "სომატური თერაპია", "სომატური თერაპევტი",
    "ფსიქოდინამიკური თერაპია", "ფსიქოანალიტიკური თერაპია",
]
THERAPY_OK: list[tuple[re.Pattern, str]] = []

# სივრცის/ორგანიზაციის საიტი (apply_site_config): FORBIDDEN_UNTIL_TEAM-ის კომპილირებული შაბლონები, რეალური
# პიროვნებების რაოდენობა ORG_MEMBERS-ში (FORBIDDEN_UNTIL_TEAM-ის „ჩვენ“-ის ტესტი ≥ 2-ზე რბილდება).
TEAM_LINT: bool = False
ORG_MODE: bool = False  # კონფიგში ORG_LEGAL_NAME — Organization + იურიდიული პირის ხაზი
FORBIDDEN_TEAM_RES: list[tuple[str, re.Pattern]] = []
ORG_MEMBER_COUNT = 0

# დემო-ვარიანტები (--demo ზოლი და --all-ის არჩევის გვერდი). bar = მოკლე სახელი დემო-ზოლში.
DEMO_SITES = [
    {"slug": "1-brendi", "label": "1 · პირადი ბრენდი", "bar": "1 ბრენდი",
     "blurb": "ერთი ადამიანი, ერთი ფასი, ერთი შეტყობინების მანძილი.",
     "compare": [("/", "მთავარი"), ("/sxeulze-orientirebuli-fsiqoterapia/", "სხეულზე ორიენტირებული"), ("/fasi/", "ფასი")]},
    {"slug": "2-biblioteka", "label": "2 · ბიბლიოთეკა", "bar": "2 ბიბლიოთეკა",
     "blurb": "ქართულენოვანი ბიბლიოთეკა ფსიქოთერაპიაზე — ყველა გვერდი ავტორიანი და წყაროებიანი.",
     "compare": [("/", "მთავარი"), ("/fsiqoterapia/", "ფსიქოთერაპია"), ("/fasi/", "ფასი")]},
    {"slug": "3-sxeuli", "label": "3 · სხეული", "bar": "3 სხეული",
     "blurb": "ფსიქოთერაპია, რომელიც სიტყვასთან ერთად სხეულსაც უსმენს.",
     "compare": [("/", "მთავარი"), ("/sxeulze-orientirebuli-fsiqoterapia/", "სხეულზე ორიენტირებული"), ("/fasi/", "ფასი")]},
    {"slug": "4-centri", "label": "4 · სივრცე", "bar": "4 სივრცე",
     "blurb": "სივრცე, რომელიც ანი ბარჯაძემ დააარსა — ღია ადგილებით კოლეგებისთვის.",
     "compare": [("/", "მთავარი"), ("/gundi/", "გუნდი"), ("/servisebi/", "სერვისები"), ("/fasi/", "ფასი")]},
]
# დემოს ფერთა პალიტრები (demo/palettes.json): ტოკენები = საიტების CSS-ის საერთო ცვლადები (--paper, --ink …).
# --line ყოველთვის ink-იდან გამოიყვანება (14%), --placeholder = --ink-soft. მხოლოდ --demo აგებაში.
PALETTES_FILE = DEMO_DIR / "palettes.json"
PALETTE_TOKENS = ["paper", "ink", "ink-soft", "accent", "accent-dark", "secondary", "surface", "surface-light",
                  "illustration-leaf", "clay"]
PALETTE_STORAGE_KEY = "ani-demo-palette"  # localStorage; ?ferebi=<id> ირჩევს, ?embed=1 — ზოლის გარეშე და შენახვის გარეშე
# ჩაშენებული <script> ბლოკების sha256 (დემოს პალიტრა) — _headers-ის CSP script-src-ში ემატება
INLINE_SCRIPT_HASHES: list[str] = []
DEMO_FORM_MSG = "დემო-რეჟიმში ფორმა არ იგზავნება"  # assets/js/main.js-შიც (data-demo)
# კითხვის სიჩქარე {{PAGE_READING_MIN}}-ისა და ბლოგის ბარათებისთვის (სიტყვა/წუთი)
WORDS_PER_MIN = 180
# shared/fonts-ის ფაილები ბრაუზერისთვის: /assets/fonts/<ფაილი>
FONTS_URL_PREFIX = "/assets/fonts/"
# ჩაშენებული <style> ბლოკების sha256 — _headers-ის CSP style-src-ში ემატება
INLINE_STYLE_HASHES: list[str] = []

# სიტყვები, რომლებიც კოპიში არ უნდა იყოს (კონცეფცია §4.4, §14.2) — WARN კონტექსტით.
CAUTION_STEMS = ["ლიცენზირებ", "ფსიქოანალიტიკოს", "განკურნ", "გარანტ", "პაციენტ", "ავადმყოფ", "მკურნალობ", "გიჟ"]

# სივრცის/ორგანიზაციის საიტი (კონფიგში FORBIDDEN_UNTIL_TEAM; საიტი 4, სპეც. §1.2): კონფიდენციალურობა არასდროს
# აბსოლუტური — ეს ფორმები ყოველთვის ERROR-ია (არა „ვერავინ გაიგონებს“ = ვერავინ მოისმენს — ის ონლაინ ოთახზეა).
ABSOLUTE_CONFIDENTIALITY_RE = re.compile(
    r"(?<![Ⴀ-ჿ])(?:ვერ|არ)ავინ\s+(?:არაფერს\s+)?(?:გაიგ(?:ებ[Ⴀ-ჿ]*|ო[სთ](?![Ⴀ-ჿ]))|შეიტყ(?:ობ[Ⴀ-ჿ]*|ო[სთ](?![Ⴀ-ჿ])))"
    r"|(?:სრულიად|აბსოლუტურად|100\s?%)\s+კონფიდენციალ[Ⴀ-ჿ]*")
# სივრცეზე სათაურში, H1-ში, SITE_NAME-სა და schema-ს სახელებში: „კლინიკა“ — არასდროს; „ცენტრი“ — მხოლოდ
# ORG_MEMBERS-ში ≥ 2 რეალური ადამიანის შემდეგ (ფაზა 2, CENTRE_DESCRIPTOR). „ლიცენზირებ“ CAUTION_STEMS-შია.
NAME_ALWAYS_FORBIDDEN = ["კლინიკ"]
NAME_FORBIDDEN_UNTIL_TEAM = ["ცენტრ"]
ORG_CAUTION_STEMS = ["აკრედიტებ"]
# schema-ში არასდროს: სამედიცინო დაწესებულების ტიპები და შეფასებები (კლიენტის შეფასებები საიტზე არ ქვეყნდება)
FORBIDDEN_SCHEMA_TYPES = {"MedicalClinic", "Hospital", "Review", "AggregateRating"}
FORBIDDEN_SCHEMA_KEYS = {"review", "aggregateRating"}
# planned გვერდი: სავალდებულო H2-ები და ინდექსირების ზღვარი (.prose-ის სიტყვები)
PLANNED_H2 = ["ვინ ატარებს", "რა შეგვიძლია დღეს"]
PLANNED_MIN_WORDS = 1000
PAGE_STATUSES = ("live", "planned")
CONTACT_FUNCTION = ROOT / "functions" / "api" / "contact.js"
DEFAULT_ROUTING_LABEL = "ვისთან გსურთ ჩაწერა?"

MONTHS_KA = ["იანვარი", "თებერვალი", "მარტი", "აპრილი", "მაისი", "ივნისი", "ივლისი",
             "აგვისტო", "სექტემბერი", "ოქტომბერი", "ნოემბერი", "დეკემბერი"]

META_RE = re.compile(r"\A\s*<!--meta\s*(\{.*?\})\s*-->", re.S)
COMMENT_RE = re.compile(r"<!--(?!\[if).*?-->", re.S)
PARTIAL_RE = re.compile(r'\{\{>\s*([\w-]+)((?:\s+[\w-]+="[^"]*")*)\s*\}\}')
PARTIAL_ARG_RE = re.compile(r'([\w-]+)="([^"]*)"')
ARG_RE = re.compile(r"\{\{@([\w-]+)(?:\|([^}]*))?\}\}")
HELPER_RE = re.compile(r"\{\{\s*(asset|nav|navgroup|navlabel):\s*([^}\s]+)\s*\}\}")
TOKEN_RE = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")
PLACEHOLDER_RE = re.compile(r"\[[^\[\]\n<>{}\"]{1,80}\]")
GEO = "Ⴀ-ჿ"
# „თერაპევტი“/„თერაპია“ ცალკე სიტყვად (არა ფსიქოთერაპია, გეშტალტთერაპია და ა.შ.)
BARE_THERAPY_RE = re.compile(rf"(?<![{GEO}])თერაპ(?:ევტ|ი)[{GEO}]*")

LEVELS = ("ERROR", "WARN", "INFO")


# ---------------------------------------------------------------- reporting
class Report:
    def __init__(self) -> None:
        self.items: list[tuple[str, str, str]] = []

    def add(self, level: str, where: str, msg: str) -> None:
        self.items.append((level, where, msg))

    def count(self, level: str) -> int:
        return sum(1 for lv, _, _ in self.items if lv == level)

    def print(self) -> None:
        by_where: dict[str, list[tuple[str, str]]] = {}
        for lv, where, msg in self.items:
            by_where.setdefault(where, []).append((lv, msg))
        for where in sorted(by_where):
            print(f"\n{where}")
            for lv, msg in sorted(by_where[where], key=lambda x: LEVELS.index(x[0])):
                print(f"  {lv:5} {msg}")
        print(f"\nშედეგი: {self.count('ERROR')} ERROR · {self.count('WARN')} WARN · {self.count('INFO')} INFO")


# ---------------------------------------------------------------- helpers
def rel(path: Path) -> str:
    """გზა ROOT-იდან (ანგარიშებისთვის); ROOT-ის გარეთ — სრული გზა."""
    try:
        return str(Path(path).resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def use_site(site_dir: Path) -> None:
    """საიტის საქაღალდის არჩევა: ყველა საიტზე დამოკიდებული გზა აქედან გამოდის."""
    global SITE_DIR, SRC, PAGES_DIR, PARTIALS_DIR, LAYOUT_FILE, ASSETS_DIR, CONFIG_FILE
    SITE_DIR = site_dir.resolve()
    SRC = SITE_DIR / "src"
    PAGES_DIR = SRC / "pages"
    PARTIALS_DIR = SRC / "partials"
    LAYOUT_FILE = SRC / "layout.html"
    ASSETS_DIR = SITE_DIR / "assets"
    CONFIG_FILE = SITE_DIR / "site.config.json"


def load_config() -> dict:
    with CONFIG_FILE.open(encoding="utf-8") as fh:
        return json.load(fh)


def apply_site_config(cfg: dict) -> None:
    """კონფიგიდან საიტის სიები: PLANNED_PATHS, NAV_GROUPS, ALLOWED_THERAPY_COMPOUNDS, SAUKETESO_ALLOWED."""
    global PLANNED_PATHS, NAV_GROUPS, NAV_GROUP_LABELS, SAUKETESO_ALLOWED, THERAPY_OK
    PLANNED_PATHS = list(cfg.get("PLANNED_PATHS", []))
    NAV_GROUPS, NAV_GROUP_LABELS = {}, {}
    for key, val in (cfg.get("NAV_GROUPS") or {}).items():
        if isinstance(val, dict):
            NAV_GROUPS[key] = list(val.get("keys", []))
            NAV_GROUP_LABELS[key] = str(val.get("label", ""))
        else:
            NAV_GROUPS[key] = list(val)
    SAUKETESO_ALLOWED = set(cfg.get("SAUKETESO_ALLOWED", DEFAULT_SAUKETESO_ALLOWED))
    THERAPY_OK = []
    for compound in cfg.get("ALLOWED_THERAPY_COMPOUNDS", DEFAULT_ALLOWED_THERAPY_COMPOUNDS):
        i = compound.find("თერაპ")
        if i <= 0:
            continue  # ერთსიტყვიანი ფორმა (ფსიქოთერაპია…) — BARE_THERAPY_RE მას ისედაც არ იჭერს
        # „ფსიქოდინამიკური (ფსიქოანალიტიკური) თერაპია“: დასაშვები განსაზღვრების შემდეგ დამხურავი ფრჩხილიც მიიღება
        prefix = r"\s+".join(re.escape(w) for w in compound[:i].split()) + (r"\)?\s+" if compound[i - 1].isspace() else "")
        stem = "თერაპევტ" if compound[i:].startswith("თერაპევტ") else "თერაპი"
        THERAPY_OK.append((re.compile(prefix + "$"), stem))
    global TEAM_LINT, ORG_MODE, FORBIDDEN_TEAM_RES, ORG_MEMBER_COUNT
    TEAM_LINT = "FORBIDDEN_UNTIL_TEAM" in cfg
    ORG_MODE = "ORG_LEGAL_NAME" in cfg
    FORBIDDEN_TEAM_RES = [(s, forbidden_phrase_re(s)) for s in cfg.get("FORBIDDEN_UNTIL_TEAM") or []
                          if isinstance(s, str) and s.strip()]
    real = person_ids(cfg) if cfg.get("SITE_URL") else {}
    ORG_MEMBER_COUNT = len({m for m in cfg.get("ORG_MEMBERS") or [] if isinstance(m, str) and m in real})


def forbidden_phrase_re(phrase: str) -> re.Pattern:
    """FORBIDDEN_UNTIL_TEAM-ის ფრაზა → შაბლონი: სიტყვის დასაწყისიდან, ჰარები = \\s+, ბოლო სიტყვა ბრუნვით
    („ჩვენი გუნდი“ → „ჩვენი გუნდის/გუნდით“, „ექსპერტები“ → „ექსპერტებს“, „რეზიდენტი“ → „რეზიდენტს“):
    ბოლო ხმოვანი ი/ა იკვეცება და მის ნაცვლად ბრუნვის/თანდებულის დაბოლოება მიიღება (არა სიტყვაწარმოება:
    „რეზიდენტურა“, „გუნდური“ არ ითვლება). „/“ სიტყვის შიგნით = ვარიანტები: „ჩვენ ვმუშაობთ ბავშვებთან/წყვილებთან“."""
    ending = rf"(?:[აეიოსმშზთდ][{GEO}]{{0,6}})?(?![{GEO}])"

    def last_word(w: str) -> str:
        if len(w) > 3 and w[-1] in "ია" and re.fullmatch(rf"[{GEO}]+", w):
            return re.escape(w[:-1]) + ending
        return re.escape(w) + (ending if re.search(rf"[{GEO}]$", w) else "")

    words = phrase.split()
    parts = []
    for i, w in enumerate(words):
        alts = [a for a in w.split("/") if a] or [w]
        alts = [last_word(a) if i == len(words) - 1 else re.escape(a) for a in alts]
        parts.append(alts[0] if len(alts) == 1 else "(?:" + "|".join(alts) + ")")
    return re.compile(rf"(?<![{GEO}])" + r"\s+".join(parts))


def asset_file(path: str) -> Path | None:
    """/assets/… URL-ის ფაილი: საიტის assets/ ან (შრიფტებისთვის) shared/fonts/."""
    if not path.startswith("/assets/"):
        return None
    file = ASSETS_DIR / path.removeprefix("/assets/")
    if file.is_file():
        return file
    if path.startswith(FONTS_URL_PREFIX):
        font = SHARED_FONTS_DIR / path.removeprefix(FONTS_URL_PREFIX)
        if font.is_file():
            return font
    return None


def is_placeholder(value) -> bool:
    if value is None:
        return True
    s = str(value).strip()
    return not s or bool(PLACEHOLDER_RE.search(s)) or "XXXX" in s or "placeholder" in s


def ka_date(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.day} {MONTHS_KA[d.month - 1]}, {d.year}"


def strip_tags(fragment: str) -> str:
    text = re.sub(r"<[^>]+>", " ", fragment)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def without_scripts(doc: str) -> str:
    return re.sub(r"<(script|style)\b.*?</\1>", " ", doc, flags=re.S | re.I)


def output_file(path: str) -> Path:
    if path.endswith(".html"):
        return DIST / path.lstrip("/")
    return DIST / path.lstrip("/") / "index.html"


def asset_url(path: str) -> str:
    file = asset_file(path)
    if not file:
        return path  # link check reports it
    digest = hashlib.sha1(file.read_bytes()).hexdigest()[:10]
    return f"{path}?v={digest}"


# ---------------------------------------------------------------- templating
def expand_partials(text: str, where: str, report: Report, stack: tuple[str, ...] = ()) -> str:
    def repl(m: re.Match) -> str:
        name, raw_args = m.group(1), m.group(2) or ""
        if name in stack or len(stack) > 8:
            report.add("ERROR", where, f"partial-ების ციკლი: {' > '.join(stack + (name,))}")
            return ""
        file = PARTIALS_DIR / f"{name}.html"
        if not file.is_file():
            report.add("ERROR", where, f"partial არ არსებობს: {{{{> {name}}}}}")
            return ""
        args = dict(PARTIAL_ARG_RE.findall(raw_args))
        body = file.read_text(encoding="utf-8")
        body = COMMENT_RE.sub("", body)
        body = ARG_RE.sub(lambda a: args.get(a.group(1), a.group(2) or ""), body)
        return expand_partials(body, where, report, stack + (name,))

    return PARTIAL_RE.sub(repl, text)


def resolve_tokens(text: str, tokens: dict[str, str], nav_key: str) -> str:
    def helper(m: re.Match) -> str:
        kind, arg = m.group(1), m.group(2)
        if kind == "asset":
            return asset_url(arg)
        if kind == "nav":
            return ' aria-current="page"' if arg == nav_key else ""
        if kind == "navgroup":
            return " is-active" if nav_key in NAV_GROUPS.get(arg, []) else ""
        if kind == "navlabel":
            return html.escape(NAV_GROUP_LABELS.get(arg, arg))
        return m.group(0)

    text = HELPER_RE.sub(helper, text)
    return TOKEN_RE.sub(lambda m: tokens.get(m.group(1), m.group(0)), text)


def config_tokens(cfg: dict) -> dict[str, str]:
    tokens = {k: str(v) for k, v in cfg.items() if not k.startswith("_") and isinstance(v, (str, int, float))}
    tokens["YEAR"] = str(date.today().year)
    tokens["TEL_URL"] = "tel:" + cfg.get("PHONE_TEL", "")
    tokens["SITE_HOST"] = urlsplit(cfg["SITE_URL"]).netloc
    tokens["ROUTING_FIELD"] = routing_field(cfg)
    return tokens


def routing_field(cfg: dict) -> str:
    """{{ROUTING_FIELD}}: ფორმის არასავალდებულო <select name="routing"> კონფიგის ROUTING_OPTIONS-იდან
    ([{"value": "ani", "label": "…"}, …]; label-ი = ROUTING_LABEL ან „ვისთან გსურთ ჩაწერა?“).
    ROUTING_OPTIONS-ის გარეშე — ცარიელი სტრიქონი (ცარიელი ხაზი აგებისას იშლება, ფორმა უცვლელია)."""
    opts = [o for o in cfg.get("ROUTING_OPTIONS") or [] if isinstance(o, dict) and o.get("value") and o.get("label")]
    if not opts:
        return ""
    esc = html.escape
    label = esc(str(cfg.get("ROUTING_LABEL") or DEFAULT_ROUTING_LABEL))
    lines = ['<div class="form__field">',
             f'    <label for="f-routing">{label} <span class="form__optional">(არასავალდებულო)</span></label>',
             '    <select id="f-routing" name="routing">',
             '      <option value="">აირჩიეთ</option>',
             *(f'      <option value="{esc(str(o["value"]))}">{esc(str(o["label"]))}</option>' for o in opts),
             '    </select>',
             '  </div>']
    return "\n".join(lines)


def contact_routing_labels() -> dict[str, str] | None:
    """functions/api/contact.js-ის ROUTING_LABELS ობიექტი ({value: label}) — ფორმის ROUTING_OPTIONS-ის შესადარებლად."""
    if not CONTACT_FUNCTION.is_file():
        return None
    m = re.search(r"const\s+ROUTING_LABELS\s*=\s*\{(.*?)\};", CONTACT_FUNCTION.read_text(encoding="utf-8"), re.S)
    if not m:
        return None
    return dict(re.findall(r"""["']?([a-z0-9-]+)["']?\s*:\s*"([^"]*)\"""", m.group(1)))


# ---------------------------------------------------------------- pages
class Page:
    def __init__(self, src: Path, meta: dict, body: str) -> None:
        self.src = src
        self.meta = meta
        self.body = body
        self.path: str = meta.get("path", "")
        self.rel = rel(src)
        self.html = ""
        self.h1_text = ""
        self.faqs: list[tuple[str, str]] = []
        self.reading_min = 1
        self.words = 0  # .prose-ის სიტყვები (prose_words)
        self.placeholders: Counter = Counter()

    @property
    def indexable(self) -> bool:
        return not self.meta.get("noindex") and not self.path.endswith(".html")

    @property
    def status(self) -> str:
        return self.meta.get("status") or "live"


def read_page(src: Path, report: Report) -> Page | None:
    where = rel(src)
    raw = src.read_text(encoding="utf-8")
    m = META_RE.match(raw)
    if not m:
        report.add("ERROR", where, "გვერდი უნდა იწყებოდეს <!--meta { JSON } --> ბლოკით")
        return None
    try:
        meta = json.loads(m.group(1))
    except json.JSONDecodeError as exc:
        report.add("ERROR", where, f"meta JSON ვერ წაიკითხა: {exc}")
        return None
    page = Page(src, meta, raw[m.end():])
    validate_meta(page, report)
    return page


def validate_meta(page: Page, report: Report) -> None:
    m, where = page.meta, page.rel
    for key in ("path", "title", "description", "h1", "type", "dateModified"):
        if not m.get(key):
            report.add("ERROR", where, f"meta.{key} აკლია")
    p = m.get("path", "")
    if p and not (p.startswith("/") and (p.endswith("/") or p.endswith(".html"))):
        report.add("ERROR", where, f"meta.path უნდა იწყებოდეს და მთავრდებოდეს „/“-ით (ან .html 404-ისთვის): {p}")
    if p and p != p.lower():
        report.add("ERROR", where, "meta.path მხოლოდ მცირე ლათინური ასოებით")
    if p and p not in PLANNED_PATHS:
        report.add("INFO", where, f"{p} არ არის PLANNED_PATHS-ში (ახალი გვერდია? დაამატეთ {rel(CONFIG_FILE)}-ში)")
    if m.get("status") is not None and m["status"] not in PAGE_STATUSES:
        report.add("ERROR", where, f"meta.status უცნობია: {m['status']} (დასაშვები: live, planned)")
    if m.get("status") == "planned":
        if m.get("type") != "WebPage":
            report.add("ERROR", where, "status: planned გვერდის type მხოლოდ WebPage (არა Service, Article, MedicalWebPage)")
        if m.get("about_service"):
            report.add("ERROR", where, "status: planned გვერდს about_service არ აქვს — დაგეგმილ სერვისს Service კვანძი არ ეკუთვნის")
    if m.get("type") and m["type"] not in PAGE_TYPES:
        report.add("ERROR", where, f"meta.type უცნობია: {m['type']} (დასაშვები: {', '.join(sorted(PAGE_TYPES))})")
    m.setdefault("datePublished", m.get("dateModified"))
    for key in ("datePublished", "dateModified", "lastReviewed"):
        if m.get(key):
            try:
                d = date.fromisoformat(m[key])
                if d > date.today():
                    report.add("WARN", where, f"meta.{key} მომავალშია: {m[key]}")
            except ValueError:
                report.add("ERROR", where, f"meta.{key} უნდა იყოს YYYY-MM-DD: {m[key]}")
    if m.get("datePublished") and m.get("dateModified") and m["datePublished"] > m["dateModified"]:
        report.add("ERROR", where, "datePublished უფრო გვიანაა, ვიდრე dateModified")
    bc = m.get("breadcrumb")
    if bc is not None and not (isinstance(bc, list) and all(isinstance(x, list) and len(x) == 2 for x in bc)):
        report.add("ERROR", where, 'meta.breadcrumb ფორმატი: [["მთავარი","/"],["ფასი","/fasi/"]]')
    if p not in ("/",) and not p.endswith(".html") and not bc:
        report.add("WARN", where, "meta.breadcrumb აკლია")
    if m.get("type") == "MedicalWebPage" and not m.get("reviewedBy"):
        report.add("WARN", where, "MedicalWebPage მხოლოდ რეალური reviewedBy-ით (კონცეფცია §11.3); სხვაგვარად type: WebPage + about_service")
    rb = m.get("reviewedBy")
    if rb and not (isinstance(rb, dict) and rb.get("name")):
        report.add("ERROR", where, 'meta.reviewedBy ფორმატი: {"name": "...", "jobTitle": "..."}')


def page_tokens(page: Page, base: dict[str, str]) -> dict[str, str]:
    m = page.meta
    t = dict(base)

    def res(s: str) -> str:
        return resolve_tokens(s, base, "")

    title, desc, h1 = res(m.get("title", "")), res(m.get("description", "")), res(m.get("h1", ""))
    m["_title"], m["_description"], m["_h1"] = title, desc, h1
    url = base["SITE_URL"] + page.path
    t.update({
        "PAGE_URL": url,
        "PAGE_PATH": page.path,
        "PAGE_TITLE": html.escape(title),
        "PAGE_DESCRIPTION": html.escape(desc),
        "PAGE_H1": html.escape(h1),
        "PAGE_DATE_PUBLISHED_ISO": m.get("datePublished", ""),
        "PAGE_DATE_MODIFIED_ISO": m.get("dateModified", ""),
        "PAGE_DATE_PUBLISHED": ka_date(m["datePublished"]) if m.get("datePublished") else "",
        "PAGE_DATE_MODIFIED": ka_date(m["dateModified"]) if m.get("dateModified") else "",
        "PAGE_SLUG": (page.path.strip("/").split("/")[0] or "home").replace(".html", ""),
        "PAGE_READING_MIN": str(page.reading_min),
        "PAGE_STATUS": page.status,
    })
    return t


def nav_key_for(page: Page) -> str:
    if page.meta.get("nav_key") is not None:
        return page.meta["nav_key"]
    first = page.path.strip("/").split("/")[0]
    return first or "home"


FAQ_RE = re.compile(
    r'<details\b[^>]*class="[^"]*\bfaq\b[^"]*"[^>]*>\s*<summary\b[^>]*>(.*?)</summary>\s*<div\b[^>]*>(.*?)</div>\s*</details>',
    re.S | re.I,
)


def render_breadcrumb(page: Page, tokens: dict[str, str]) -> str:
    bc = page.meta.get("breadcrumb") or []
    if len(bc) < 2 or page.meta.get("breadcrumb_visible") is False:
        return ""
    items = []
    for i, (name, href) in enumerate(bc):
        name = html.escape(resolve_tokens(name, tokens, ""))
        if i == len(bc) - 1:
            items.append(f'<li><span aria-current="page">{name}</span></li>')
        else:
            items.append(f'<li><a href="{href}">{name}</a></li>')
    return ('<nav class="breadcrumb container" aria-label="ნავიგაციის ჯაჭვი"><ol>'
            + "".join(items) + "</ol></nav>")


# ---------------------------------------------------------------- reading time, blog cards
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
WORD_RE = re.compile(r"\w+(?:[-‐'’]\w+)*")


class ProseText(HTMLParser):
    """ტექსტი მხოლოდ class="prose" ელემენტების შიგნით (script/style-ის გარეშე)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.depth = 0  # >0 = .prose-ის შიგნით ვართ (ღია ტეგების რაოდენობა)
        self.skip = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in VOID_TAGS:
            return
        if tag in ("script", "style"):
            self.skip += 1
        if self.depth:
            self.depth += 1
        elif "prose" in (dict(attrs).get("class") or "").split():
            self.depth = 1

    def handle_endtag(self, tag):
        if tag in VOID_TAGS:
            return
        if tag in ("script", "style") and self.skip:
            self.skip -= 1
        if self.depth:
            self.depth -= 1

    def handle_data(self, data):
        if self.depth and not self.skip:
            self.parts.append(data)


def prose_words(page: Page) -> int:
    """.prose ტექსტის სიტყვები (partial-ები და ტოკენები არ ითვლება) — წაკითხვის დრო და planned გვერდის ზღვარი."""
    body = COMMENT_RE.sub("", page.body)
    body = PARTIAL_RE.sub(" ", body)
    body = re.sub(r"\{\{[^{}]*\}\}", " ", body)
    parser = ProseText()
    parser.feed(body)
    return len(WORD_RE.findall(" ".join(parser.parts)))


def reading_minutes(page: Page) -> int:
    """.prose ტექსტის სიტყვები ÷ WORDS_PER_MIN (მინიმუმ 1)."""
    page.words = prose_words(page)
    return max(1, int(page.words / WORDS_PER_MIN + 0.5))


def blog_cards(cfg: dict, report: Report) -> str:
    """{{BLOG_CARDS}}: ARTICLES ახლიდან ძველისკენ. ბარათის ტექსტი = meta.card_summary ან meta.description."""
    esc = html.escape
    author = (f'<a href="{esc(cfg.get("AUTHOR_PATH", "/chems-shesakheb/"))}">{esc(cfg["NAME"])}</a>')
    items = []
    for a in sorted(ARTICLES, key=lambda a: (a.meta["datePublished"], a.path), reverse=True):
        m = a.meta
        if not m.get("kicker"):
            report.add("WARN", a.rel, "meta.kicker აკლია — ბლოგის ბარათზე თემა არ გამოჩნდება")
        kicker = f'\n  <p class="card__kicker">{esc(m["kicker"])}</p>' if m.get("kicker") else ""
        text = m.get("card_summary") or m["_description"]
        items.append(
            f'<li class="card">{kicker}\n'
            f'  <h3 class="card__title"><a href="{a.path}">{esc(m["_h1"])}</a></h3>\n'
            f'  <p>{esc(text)}</p>\n'
            f'  <p class="card__meta"><time datetime="{m["datePublished"]}">{ka_date(m["datePublished"])}</time>'
            f' · წაკითხვის დრო: {a.reading_min} წუთი · ავტორი: {author}</p>\n'
            f'</li>')
    if not items:
        return ""
    return '<ul class="cards">\n' + "\n".join(items) + "\n</ul>"


# ---------------------------------------------------------------- JSON-LD
def person_ids(cfg: dict) -> dict[str, str]:
    """რეალური პიროვნებების id → JSON-LD @id: მთავარი პიროვნება (PERSON_ID, ნაგულისხმევი „person-ani“ → #ani)
    და PEOPLE-ის ჩანაწერები (#<id>). ღია ადგილი პიროვნება არ არის — მას id არ აქვს."""
    site = cfg["SITE_URL"]
    ids = {str(cfg.get("PERSON_ID") or "person-ani"): f"{site}/#ani"}
    for x in cfg.get("PEOPLE") or []:
        if isinstance(x, dict) and x.get("id") and not is_placeholder(x.get("name")):
            ids.setdefault(str(x["id"]), f"{site}/#{x['id']}")
    return ids


def build_graph(page: Page, cfg: dict, tokens: dict[str, str]) -> dict:
    site = cfg["SITE_URL"]
    m = page.meta
    url = tokens["PAGE_URL"]
    pid, ani, web = f"{site}/#practice", f"{site}/#ani", f"{site}/#website"

    def filled(key: str) -> bool:
        return not is_placeholder(cfg.get(key))

    photo = cfg.get("PHOTO_PORTRAIT", "")
    real_photo = photo and "placeholder" not in photo
    same_as = [cfg["FACEBOOK_URL"]] + [u for u in cfg.get("SAME_AS", []) if not is_placeholder(u)]
    price_value = str(cfg.get("PRICE_VALUE", "")).strip()

    org = "ORG_LEGAL_NAME" in cfg  # სივრცე/ორგანიზაცია (საიტი 4): name = SITE_NAME, დამფუძნებელი = Person
    planned = page.status == "planned"  # დაგეგმილ გვერდზე Service/Offer კვანძი არ არის
    people = person_ids(cfg)

    practice: dict = {
        "@type": ["Organization", "MedicalBusiness"] if org else "MedicalBusiness",
        "@id": pid,
        "name": cfg["SITE_NAME"] if org else cfg["PRACTICE_NAME"],
        "alternateName": cfg["NAME_LATIN"],
        "description": cfg["SITE_DESCRIPTION"],
        "url": f"{site}/",
        "email": cfg["EMAIL"],
        "address": {
            "@type": "PostalAddress",
            "streetAddress": cfg["STREET"],
            "addressLocality": cfg["CITY"],
            "postalCode": cfg["POSTAL_CODE"],
            "addressCountry": "GE",
        },
        "geo": {"@type": "GeoCoordinates", "latitude": cfg["GEO_LAT"], "longitude": cfg["GEO_LNG"]},
        "hasMap": cfg["MAPS_URL"],
        "areaServed": [{"@type": "City", "name": cfg["CITY"]}, {"@type": "Country", "name": "საქართველო"}],
        "knowsLanguage": "ka",
        "currenciesAccepted": "GEL",
        "founder": {"@id": ani},
        "sameAs": same_as,
        "hasOfferCatalog": {
            "@type": "OfferCatalog",
            "name": "მომსახურება",
            "itemListElement": [
                {"@type": "Offer", "itemOffered": {"@id": f"{site}/#{s['id']}"}} for s in cfg.get("SERVICES", [])
            ],
        },
    }
    if org:
        practice.pop("alternateName")  # NAME_LATIN ადამიანის სახელია, არა სივრცის
        for key, prop in (("ORG_LEGAL_NAME", "legalName"), ("ORG_TAX_ID", "taxID"), ("ORG_FOUNDED", "foundingDate")):
            if filled(key):  # taxID: მხოლოდ ნომერი (კონფიგში იარლიყით: „ს/კ 000000000“ / „პ/ნ 00000000000“)
                practice[prop] = re.sub(r"^\D+(?=\d)", "", str(cfg[key]).strip()) if prop == "taxID" else str(cfg[key])
        members = [people[i] for i in cfg.get("ORG_MEMBERS") or [] if i in people]
        if members:
            practice["member"] = [{"@id": i} for i in members]
    if planned:
        practice.pop("hasOfferCatalog")
    if filled("PHONE_TEL"):
        practice["telephone"] = cfg["PHONE_TEL"]
    if filled("PRICE"):
        practice["priceRange"] = cfg["PRICE"]
    if cfg.get("OPENING_HOURS_SPEC") and filled("HOURS"):
        practice["openingHoursSpecification"] = cfg["OPENING_HOURS_SPEC"]
    if real_photo:
        practice["image"] = site + photo

    person: dict = {
        "@type": "Person",
        "@id": ani,
        "name": cfg["NAME"],
        "alternateName": cfg["NAME_LATIN"],
        "jobTitle": cfg["ROLE"],
        "hasOccupation": {"@type": "Occupation", "name": cfg["ROLE"]},
        "knowsAbout": ["გეშტალტთერაპია", "სხეულზე ორიენტირებული ფსიქოთერაპია", "შფოთვა", "პანიკური შეტევები"],
        "knowsLanguage": "ka",
        "url": site + cfg.get("AUTHOR_PATH", "/chems-shesakheb/"),
        "worksFor": {"@id": pid},
        "sameAs": [cfg["FACEBOOK_URL"]],
    }
    if org:
        person["memberOf"] = {"@id": pid}
    if real_photo:
        person["image"] = site + photo
    extra_people = [{"@type": "Person", "@id": people[x["id"]], "name": x["name"], "jobTitle": x["jobTitle"],
                     "url": site + x["url"], "worksFor": {"@id": pid}, "memberOf": {"@id": pid}}
                    for x in cfg.get("PEOPLE") or [] if x.get("id") in people and x["id"] in (cfg.get("ORG_MEMBERS") or [])]

    website = {
        "@type": "WebSite",
        "@id": web,
        "url": f"{site}/",
        "name": cfg["SITE_NAME"],
        "inLanguage": "ka",
        "publisher": {"@id": pid},
    }

    services = []
    for s in ([] if planned else cfg.get("SERVICES", [])):
        node = {
            "@type": "Service",
            "@id": f"{site}/#{s['id']}",
            "serviceType": s.get("serviceType") or s["name"],
            "name": s["name"],
            "url": site + s["path"],
            "provider": {"@id": people.get(s.get("provider"), pid)},
            "areaServed": {"@type": "City", "name": cfg["CITY"]},
            "availableChannel": [
                {"@type": "ServiceChannel", "name": f"კაბინეტში, {cfg['STREET']}"},
                {"@type": "ServiceChannel", "name": "ონლაინ (ვიდეოზარი)"},
            ],
        }
        if re.fullmatch(r"\d+(?:\.\d+)?", price_value):
            node["offers"] = {
                "@type": "Offer",
                "price": price_value,
                "priceCurrency": "GEL",
                "description": f"1 სესია, {cfg['SESSION_MIN']} წუთი",
                "url": f"{site}/fasi/",
            }
        services.append(node)

    ptype = m.get("type", "WebPage")
    page_node: dict = {
        "@type": "WebPage" if ptype == "Article" else ptype,
        "@id": f"{url}#webpage",
        "url": url,
        "name": m["_title"],
        "description": m["_description"],
        "inLanguage": "ka",
        "isPartOf": {"@id": web},
        "datePublished": m.get("datePublished"),
        "dateModified": m.get("dateModified"),
        "author": {"@id": ani},
    }
    if page.path == "/":
        page_node["about"] = {"@id": pid}
    elif ptype == "AboutPage":
        page_node["about"] = {"@id": ani}
        page_node["mainEntity"] = {"@id": ani}
    elif ptype == "ContactPage":
        page_node["about"] = {"@id": pid}
    if m.get("about_service"):
        page_node["about"] = {"@id": f"{site}/#{m['about_service']}"}
    if m.get("reviewedBy"):
        rb = m["reviewedBy"]
        page_node["reviewedBy"] = {"@type": "Person", **{k: v for k, v in rb.items() if k in ("name", "jobTitle", "url")}}
        if m.get("lastReviewed"):
            page_node["lastReviewed"] = m["lastReviewed"]
    og = m.get("og_image") or cfg["OG_IMAGE"]
    page_node["primaryImageOfPage"] = {"@type": "ImageObject", "url": site + og}

    bc = m.get("breadcrumb") or []
    graph = [practice, person, *extra_people, website, *services, page_node]
    if len(bc) >= 2:
        page_node["breadcrumb"] = {"@id": f"{url}#breadcrumb"}
        graph.append({
            "@type": "BreadcrumbList",
            "@id": f"{url}#breadcrumb",
            "itemListElement": [
                {"@type": "ListItem", "position": i + 1,
                 "name": resolve_tokens(name, tokens, ""), "item": site + href}
                for i, (name, href) in enumerate(bc)
            ],
        })

    if ptype == "Article":
        graph.append({
            "@type": "Article",
            "@id": f"{url}#article",
            "headline": m["_h1"],
            "description": m["_description"],
            "inLanguage": "ka",
            "author": {"@id": ani},
            "publisher": {"@id": pid},
            "datePublished": m.get("datePublished"),
            "dateModified": m.get("dateModified"),
            "image": site + og,
            "mainEntityOfPage": {"@id": f"{url}#webpage"},
        })

    if ptype == "CollectionPage" and page.path == "/blogi/" and ARTICLES:
        page_node["hasPart"] = [{"@id": f"{site}{a.path}#article"} for a in ARTICLES]
        page_node["mainEntity"] = {
            "@type": "ItemList",
            "itemListElement": [
                {"@type": "ListItem", "position": i + 1, "url": site + a.path, "name": a.meta["_h1"]}
                for i, a in enumerate(ARTICLES)
            ],
        }

    if page.faqs and (len(page.faqs) >= 3 or ptype == "FAQPage"):
        questions = [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}}
            for q, a in page.faqs
        ]
        if "mainEntity" in page_node and ptype != "FAQPage":
            # AboutPage (Person) ან CollectionPage უკვე იყენებს mainEntity-ს — FAQ ცალკე კვანძად, არ ვანაცვლებთ
            graph.append({"@type": "FAQPage", "@id": f"{url}#faq", "url": url, "inLanguage": "ka",
                          "isPartOf": {"@id": f"{url}#webpage"}, "mainEntity": questions})
        else:
            if ptype != "FAQPage":
                page_node["@type"] = [page_node["@type"], "FAQPage"]
            page_node["mainEntity"] = questions

    if m.get("noindex"):
        # noindex გვერდზე (404) სრული ბიზნეს-გრაფი ზედმეტია — მხოლოდ WebSite + WebPage
        page_node.pop("breadcrumb", None)
        page_node.pop("primaryImageOfPage", None)
        page_node.pop("author", None)
        site_node = {k: v for k, v in website.items() if k != "publisher"}  # #practice ამ გრაფში არ არის
        return {"@context": "https://schema.org", "@graph": [site_node, page_node]}
    return {"@context": "https://schema.org", "@graph": graph}


# ---------------------------------------------------------------- render
GLUED_LINK_SPAN_RE = re.compile(r"</a><span(?=[\s>])")
GLUED_LABEL_RE = re.compile(r'(<span class="facts__label">[^<]*</span>)(?=[^\s<]|<a\b)')


def separate_glued_text(html_text: str) -> str:
    """ბმული + აღწერა („დაკავშირებული“) და .facts__label + ტექსტი HTML-ში ჰარის გარეშე იდგა.
    CSS მათ ცალ-ცალკე ხაზზე აჩენს, მაგრამ CSS-ის გარეშე წამკითხველები (AI-ბოტები, textContent)
    სიტყვებს აწებებდნენ („მიმდინარეობს50“, „პრაქტიკაკერძო“). ერთი ჰარი ვიზუალს არ ცვლის — ორივე span ბლოკურია."""
    html_text = GLUED_LINK_SPAN_RE.sub("</a> <span", html_text)
    return GLUED_LABEL_RE.sub(r"\1 ", html_text)


def render(page: Page, cfg: dict, base_tokens: dict[str, str], report: Report, demo: bool = False) -> None:
    tokens = page_tokens(page, base_tokens)
    nav_key = nav_key_for(page)
    body = COMMENT_RE.sub("", page.body)
    body = expand_partials(body, page.rel, report)
    body = resolve_tokens(body, tokens, nav_key)

    page.faqs = [(strip_tags(q), strip_tags(a)) for q, a in FAQ_RE.findall(body)]
    graph = build_graph(page, cfg, tokens)
    json_ld = json.dumps(graph, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")

    m = page.meta
    og_image = cfg["SITE_URL"] + (m.get("og_image") or cfg["OG_IMAGE"])
    if demo:  # დემო: არცერთი გვერდი არ ინდექსირდება (meta.noindex-ს არ ვცვლით — ARTICLES/JSON-LD უცვლელია)
        robots = "noindex, nofollow"
    else:
        robots = "noindex, follow" if m.get("noindex") else "index, follow, max-image-preview:large"
    head_extra = []
    if m.get("type") == "Article":
        head_extra.append(f'<meta property="article:published_time" content="{m["datePublished"]}">')
        head_extra.append(f'<meta property="article:modified_time" content="{m["dateModified"]}">')
    sticky = "" if m.get("sticky_cta") is False else expand_partials("{{> sticky-cta}}", page.rel, report)

    canonical = "" if (demo or m.get("noindex")) else f'<link rel="canonical" href="{tokens["PAGE_URL"]}">'
    tokens.update({
        "PAGE_CANONICAL": canonical,
        "PAGE_ROBOTS": robots,
        "PAGE_OG_TYPE": "article" if m.get("type") == "Article" else "website",
        "PAGE_OG_IMAGE": og_image,
        "PAGE_HEAD_EXTRA": "\n".join(head_extra),
        "BREADCRUMB": render_breadcrumb(page, tokens),
        "STICKY_CTA": resolve_tokens(sticky, tokens, nav_key),
        "JSON_LD": json_ld,
        "CONTENT": body.strip(),
    })
    layout = LAYOUT_FILE.read_text(encoding="utf-8")
    layout = COMMENT_RE.sub("", layout)
    layout = expand_partials(layout, page.rel, report)
    # ერთი გავლა: ჩასმული CONTENT/JSON_LD აღარ მუშავდება ხელახლა
    page.html = resolve_tokens(layout, tokens, nav_key)
    page.html = re.sub(r"\n\s*\n+", "\n", page.html).lstrip()
    page.html = separate_glued_text(page.html)


# ---------------------------------------------------------------- validation
class DocParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str, dict]] = []
        self.ids: list[str] = []
        self.imgs: list[dict] = []
        self.anchor_texts: list[str] = []
        self.blank_targets: list[str] = []
        self._a_depth = 0
        self._a_buf: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if tag in ("script", "style"):
            self._skip += 1
        if "id" in a:
            self.ids.append(a["id"])
        for attr in ("href", "src", "action"):
            if attr in a and not (tag == "script" and a.get("type") == "application/ld+json"):
                self.links.append((tag, a[attr], a))
        if "srcset" in a:
            for part in a["srcset"].split(","):
                if part.strip():
                    self.links.append((tag, part.strip().split()[0], a))
        if tag == "img":
            self.imgs.append(a)
        if tag == "a":
            self._a_depth += 1
            self._a_buf = []
            if a.get("target") == "_blank" and "noopener" not in a.get("rel", ""):
                self.blank_targets.append(a.get("href", ""))

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1
        if tag == "a" and self._a_depth:
            self._a_depth -= 1
            self.anchor_texts.append(re.sub(r"\s+", " ", "".join(self._a_buf)).strip())

    def handle_data(self, data):
        if self._a_depth and not self._skip:
            self._a_buf.append(data)


def bare_therapy_hits(text: str) -> list[str]:
    hits = []
    for mt in BARE_THERAPY_RE.finditer(text):
        before = text[: mt.start()]
        if not any(mt.group(0).startswith(stem) and rx.search(before) for rx, stem in THERAPY_OK):
            hits.append(mt.group(0))
    return hits


def check_link(url: str, page: Page, ctx: dict, report: Report) -> None:
    where = page.rel
    if not url or url.startswith(("#", "mailto:", "tel:", "data:", "sms:")):
        return
    if url.lower().startswith("javascript:"):
        report.add("ERROR", where, f"javascript: ბმული: {url}")
        return
    if "XXXX" in url:
        return  # ტელეფონის ნომერი — ცალკე ჩანაწერად ჩანს placeholder-ების სიაში
    if PLACEHOLDER_RE.search(url):
        ctx["placeholder_links"].add(url)
        return
    parts = urlsplit(url)
    site_host = urlsplit(ctx["site_url"]).netloc
    path = unquote(parts.path)
    if parts.scheme in ("http", "https") or url.startswith("//"):
        if parts.netloc not in (site_host, "www." + site_host):
            if parts.scheme == "http":
                report.add("WARN", where, f"http:// გარე ბმული (გამოიყენეთ https): {url}")
            return
        # იმავე ჰოსტის აბსოლუტური URL (canonical): --site-url-ის ბაზის გზა შედარებამდე მოიხსნება
        if BASE_PATH and (path == BASE_PATH or path.startswith(BASE_PATH + "/")):
            path = path[len(BASE_PATH):] or "/"
    if not path:
        return
    if not path.startswith("/"):
        report.add("WARN", where, f"ფარდობითი ბმული — გამოიყენეთ „/“-ით დაწყებული: {url}")
        path = posixpath.normpath(posixpath.join(posixpath.dirname(page.path), path))
    if path == "/en" or path.startswith("/en/"):
        report.add("ERROR", where, f"საიტი მხოლოდ ქართულია — /en/ ბმული აკრძალულია: {url}")
        return
    if path.startswith("/assets/"):
        if not asset_file(path):
            report.add("ERROR", where, f"ასეტი არ არსებობს: {url}")
        elif "placeholder" in path:
            ctx["placeholder_links"].add(f"დროებითი სურათი {posixpath.basename(path)}")
        return
    if path in KNOWN_ENDPOINTS or path in ctx["built"]:
        return
    if path in PLANNED_PATHS:
        level = "ERROR" if ctx["release"] else ("INFO" if ctx["single"] else "WARN")
        ctx["planned_hits"].setdefault(path, level)
        return
    if not path.endswith("/") and (path + "/") in (set(ctx["built"]) | set(PLANNED_PATHS)):
        report.add("WARN", where, f"ბმულს ბოლოში „/“ აკლია: {url}")
        return
    report.add("ERROR", where, f"გატეხილი შიდა ბმული: {url}")


def validate(page: Page, ctx: dict, report: Report) -> None:
    where, doc, m = page.rel, page.html, page.meta
    visible = without_scripts(doc)

    # <title>
    tm = re.search(r"<title>(.*?)</title>", doc, re.S)
    title = html.unescape(tm.group(1)).strip() if tm else ""
    if not title:
        report.add("ERROR", where, "<title> ცარიელია")
    elif len(title) > 70:
        report.add("ERROR", where, f"სათაური ძალიან გრძელია ({len(title)} > 70): {title}")
    elif len(title) > 50:
        report.add("WARN", where, f"სათაური {len(title)} სიმბოლოა (> 50; ~600px ტესტი): {title}")

    desc = m.get("_description", "")
    if not 70 <= len(desc) <= 170:
        report.add("WARN", where, f"description {len(desc)} სიმბოლოა (სასურველია 70–170)")

    # H1
    h1s = re.findall(r"<h1\b[^>]*>(.*?)</h1>", doc, re.S | re.I)
    if len(h1s) != 1:
        report.add("ERROR", where, f"გვერდზე უნდა იყოს ზუსტად ერთი <h1> (ნაპოვნია {len(h1s)})")
    else:
        page.h1_text = strip_tags(h1s[0]).replace("\u00ad", "")  # &shy; = მხოლოდ გადატანის მინიშნება
        if page.h1_text != re.sub(r"\s+", " ", m.get("_h1", "")).strip():
            report.add("ERROR", where, f"<h1> არ ემთხვევა meta.h1-ს:\n          HTML: {page.h1_text}\n          meta: {m.get('_h1')}")

    # tokens, hreflang
    leftovers = sorted(set(re.findall(r"\{\{[^{}]*\}\}|\{\{|\}\}", visible)))
    if leftovers:
        report.add("ERROR", where, f"გადაუწყვეტელი ტოკენები: {', '.join(leftovers[:8])}")
    if re.search(r"hreflang", doc, re.I):
        report.add("ERROR", where, "hreflang აკრძალულია (საიტი მხოლოდ ქართულია)")

    # JSON-LD
    blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', doc, re.S)
    if len(blocks) != 1:
        report.add("ERROR", where, f"უნდა იყოს ზუსტად ერთი JSON-LD ბლოკი (ნაპოვნია {len(blocks)})")
    schema_names: list[str] = []
    for b in blocks:
        try:
            data = json.loads(b.replace("<\\/", "</"))
            for node in data.get("@graph", []):
                for key in ("name", "headline", "serviceType"):
                    if isinstance(node.get(key), str):
                        schema_names.append(node[key])
                types = node.get("@type")
                bad = (set(types) if isinstance(types, list) else {types}) & FORBIDDEN_SCHEMA_TYPES
                bad |= FORBIDDEN_SCHEMA_KEYS & set(node)
                if bad:
                    report.add("ERROR", where, f"JSON-LD: {', '.join(sorted(bad))} აკრძალულია (არც კლინიკა, არც შეფასებები)")
        except json.JSONDecodeError as exc:
            report.add("ERROR", where, f"JSON-LD ვერ წაიკითხა: {exc}")
    if m.get("type") == "Article" and len(m.get("_h1", "")) > 110:
        report.add("WARN", where, "Article headline (H1) > 110 სიმბოლო")
    if m.get("type") == "FAQPage" and len(page.faqs) < 3:
        report.add("WARN", where, "type FAQPage, მაგრამ <details class=\"faq\"> 3-ზე ნაკლებია")

    # parser-based checks
    parser = DocParser()
    parser.feed(doc)
    for tag, url, _ in parser.links:
        check_link(url, page, ctx, report)
    dupes = sorted({i for i in parser.ids if parser.ids.count(i) > 1})
    if dupes:
        report.add("ERROR", where, f"განმეორებადი id: {', '.join(dupes)}")
    for img in parser.imgs:
        if "alt" not in img:
            report.add("ERROR", where, f"<img> alt-ის გარეშე: {img.get('src')}")
        if not (img.get("width") and img.get("height")):
            report.add("WARN", where, f"<img> width/height-ის გარეშე (CLS): {img.get('src')}")
    for href in parser.blank_targets:
        report.add("WARN", where, f'target="_blank" rel="noopener"-ის გარეშე: {href}')

    # „თერაპევტი“ / „თერაპია“ ცალკე
    nav_html = "".join(re.findall(r'<nav\b[^>]*class="[^"]*site-nav[^"]*".*?</nav>', doc, re.S))
    scopes = {"<title>": [title], "<h1>": [page.h1_text], "ნავიგაცია": [strip_tags(nav_html)],
              "ბმულის ტექსტი": parser.anchor_texts, "schema name": schema_names}
    for scope, texts in scopes.items():
        for text in texts:
            hits = bare_therapy_hits(text or "")
            if hits:
                report.add("ERROR", where, f"„{hits[0]}“ ცალკე სიტყვად ({scope}): {text[:90]}")

    text = strip_tags(visible)
    if "საუკეთესო" in text and page.path not in SAUKETESO_ALLOWED and not m.get("allow_sauketeso"):
        report.add("WARN", where, "„საუკეთესო“ — დასაშვებია მხოლოდ გზამკვლევში, არასდროს ანიზე")
    for stem in CAUTION_STEMS:
        for mt in re.finditer(rf"[{GEO}]*{stem}[{GEO}]*", text):
            ctx_s = text[max(0, mt.start() - 40): mt.end() + 40]
            report.add("WARN", where, f"სიფრთხილის სიტყვა „{mt.group(0)}“: …{ctx_s}…")
            break

    if TEAM_LINT:
        team_checks(page, f"{text} {desc}", {"<title>": [title], "<h1>": [page.h1_text], "schema name": schema_names}, report)
    if page.status == "planned":
        planned_checks(page, doc, report)

    if m.get("type") in ("Article", "MedicalWebPage"):
        if 'class="short-answer' not in doc:
            report.add("WARN", where, "„მოკლე პასუხი“ ბლოკი (.short-answer) აკლია")
        if 'class="author-box' not in doc:
            report.add("WARN", where, "ავტორის ბარათი ({{> author-box}}) აკლია")

    # placeholders (INFO); რაოდენობები --placeholders-report-ისთვის
    counts = Counter(PLACEHOLDER_RE.findall(text))
    for attr_val in re.findall(r'(?:href|src|alt|content|title|aria-label)="([^"]*)"', visible):
        counts.update(PLACEHOLDER_RE.findall(html.unescape(attr_val)))
    counts.update(ctx.pop("placeholder_links", set()))
    ctx["placeholder_links"] = set()
    phones = len(re.findall(r"X{6,}", visible))
    if phones:
        counts["ტელეფონის ნომერი (995XXXXXXXXX: tel/WhatsApp)"] += phones
    page.placeholders = counts
    found = set(counts)
    if found:
        level = "ERROR" if ctx["release"] else "INFO"
        report.add(level, where, "შესავსები ადგილები: " + " · ".join(sorted(found)))


def team_checks(page: Page, text: str, name_scopes: dict[str, list[str]], report: Report) -> None:
    """სივრცის საიტი (FORBIDDEN_UNTIL_TEAM): „ჩვენ“-ის ტესტი, აბსოლუტური კონფიდენციალურობა, „ცენტრი/კლინიკა“ სახელებში."""
    where, m = page.rel, page.meta

    def around(mt: re.Match) -> str:
        return text[max(0, mt.start() - 40): mt.end() + 40]

    for mt in ABSOLUTE_CONFIDENTIALITY_RE.finditer(text):
        report.add("ERROR", where, f"კონფიდენციალურობა აბსოლუტური ფორმით „{mt.group(0)}“ — ჩაანაცვლეთ "
                                   f"{{{{CONFIDENTIALITY_LINE}}}}-ით (გამონაკლისები კანონით): …{around(mt)}…")
    if ORG_MEMBER_COUNT < 2:
        allowed = set(m.get("allow_forbidden") or [])
        for phrase, rx in FORBIDDEN_TEAM_RES:
            if ABSOLUTE_CONFIDENTIALITY_RE.fullmatch(phrase):
                continue  # ზემოთ უკვე შემოწმდა (ყოველთვის, ORG_MEMBERS-ის მიუხედავად)
            mt = rx.search(text)
            if not mt:
                continue
            if phrase in allowed:
                report.add("INFO", where, f"„{mt.group(0)}“ დაშვებულია meta.allow_forbidden-ით (მხოლოდ ციტატა/კითხვა, არა სივრცეზე)")
                continue
            report.add("ERROR", where, f"„{mt.group(0)}“ — FORBIDDEN_UNTIL_TEAM: დასაშვებია მხოლოდ მაშინ, როცა ORG_MEMBERS-ში "
                                       f"≥ 2 რეალური ადამიანია („ჩვენ“ = ანი + სახლის წესები): …{around(mt)}…")
    stems = NAME_ALWAYS_FORBIDDEN + (NAME_FORBIDDEN_UNTIL_TEAM if ORG_MEMBER_COUNT < 2 else [])
    for scope, texts in name_scopes.items():
        for t in texts:
            hit = next((st for st in stems if st in (t or "")), None)
            if hit:
                report.add("ERROR", where, f"„{hit}…“ სივრცის სახელში ({scope}) — „კლინიკა“ არასდროს, „ცენტრი“ მხოლოდ "
                                           f"ფაზა 2-ში (ORG_MEMBERS ≥ 2): {t[:90]}")
    for stem in ORG_CAUTION_STEMS:
        mt = re.search(rf"[{GEO}]*{stem}[{GEO}]*", text)
        if mt:
            report.add("WARN", where, f"სიფრთხილის სიტყვა „{mt.group(0)}“ — სივრცეზე „ლიცენზირებული/აკრედიტებული“ არასდროს: …{around(mt)}…")
    if ORG_MODE and 'class="entity-line' not in page.html:
        report.add("WARN", where, "იურიდიული პირის ხაზი ({{> entity-line}}, class=\"entity-line\") გვერდზე არ ჩანს — ფუტერში უნდა იყოს")


def planned_checks(page: Page, doc: str, report: Report) -> None:
    """status: planned — „დაგეგმილია — ადგილი ღიაა“ მექანიზმი (სპეც. §1.2): ბეჯი, ვინ ატარებს, ხიდი, უსაფრთხოება."""
    where = page.rel
    if not (re.search(r"\{\{>\s*status-planned\b", page.body) or "status--planned" in doc):
        report.add("ERROR", where, "status: planned გვერდს {{> status-planned}} ბეჯი აკლია (H1-ის გვერდით)")
    h2s = [strip_tags(h) for h in re.findall(r"<h2\b[^>]*>(.*?)</h2>", doc, re.S | re.I)]
    for need in PLANNED_H2:
        if not any(h.startswith(need) for h in h2s):
            report.add("ERROR", where, f"status: planned გვერდს H2 „{need}“ აკლია")
    if not (re.search(r"\{\{>\s*safety\b", page.body) or "callout-safety" in doc):
        report.add("ERROR", where, "status: planned გვერდს უსაფრთხოების ბლოკი ({{> safety}}) აკლია")


def site_checks(pages: list[Page], cfg: dict, report: Report) -> None:
    seen_t: dict[str, str] = {}
    seen_d: dict[str, str] = {}
    seen_p: dict[str, str] = {}
    for p in pages:
        for store, key, label in ((seen_t, "_title", "სათაური"), (seen_d, "_description", "description")):
            val = p.meta.get(key)
            if val and val in store:
                report.add("ERROR", p.rel, f"{label} მეორდება ({store[val]})")
            elif val:
                store[val] = p.rel
        if p.path in seen_p:
            report.add("ERROR", p.rel, f"path {p.path} მეორდება ({seen_p[p.path]})")
        seen_p[p.path] = p.rel
    phone = re.sub(r"\D", "", cfg.get("PHONE_TEL", ""))
    wa = re.search(r"wa\.me/(\d+)", cfg.get("WA_URL", ""))
    if phone and wa and not is_placeholder(cfg.get("PHONE_TEL")) and wa.group(1) != phone:
        report.add("ERROR", rel(CONFIG_FILE), "WA_URL-ის ნომერი PHONE_TEL-ს არ ემთხვევა")
    config_checks(pages, cfg, report)


def config_checks(pages: list[Page], cfg: dict, report: Report) -> None:
    """კონფიგის ახალი გასაღებების შემოწმება — მხოლოდ მაშინ, როცა გასაღები კონფიგშია (საიტები 1–3 უცვლელია)."""
    where = rel(CONFIG_FILE)
    err = lambda msg: report.add("ERROR", where, msg)  # noqa: E731
    for key, val in cfg.items():
        if not key.startswith("_") and isinstance(val, str) and "{{" in val:
            err(f"{key}: ტოკენი ტოკენის შიგნით არ იხსნება (resolve_tokens ერთგავლიანია) — გამოიყენეთ partial, "
                "მაგ. იურიდიული ხაზისთვის {{> entity-line}}")
    if cfg.get("CENTRE_NAME") and cfg.get("CENTRE_DESCRIPTOR"):
        full = f"{cfg['CENTRE_NAME']} — {cfg['CENTRE_DESCRIPTOR']}"
        if cfg.get("SITE_NAME") != full:
            err(f"SITE_NAME უნდა იყოს „CENTRE_NAME — CENTRE_DESCRIPTOR“ = „{full}“ (სრული ფორმა, არასდროს მარტო სახელი)")
        if ORG_MODE and cfg.get("PRACTICE_NAME") not in (None, full):
            report.add("WARN", where, f"PRACTICE_NAME ≠ SITE_NAME („{full}“) — ორგანიზაციის სახელი ერთი უნდა იყოს")
    if TEAM_LINT:
        if not isinstance(cfg.get("FORBIDDEN_UNTIL_TEAM"), list) or not all(
                isinstance(x, str) for x in cfg["FORBIDDEN_UNTIL_TEAM"]):
            err("FORBIDDEN_UNTIL_TEAM უნდა იყოს სტრიქონების სია")
        for key in ("SITE_NAME", "OG_IMAGE_ALT", "CENTRE_DESCRIPTOR"):
            stems = NAME_ALWAYS_FORBIDDEN + (NAME_FORBIDDEN_UNTIL_TEAM if ORG_MEMBER_COUNT < 2 else [])
            hit = next((st for st in stems if st in str(cfg.get(key, ""))), None)
            if hit:
                err(f"{key}: „{hit}…“ — „კლინიკა“ არასდროს, „ცენტრი“ მხოლოდ ფაზა 2-ში (ORG_MEMBERS-ში ≥ 2 რეალური ადამიანი)")

    people = person_ids(cfg)
    for i, x in enumerate(cfg.get("PEOPLE") or []):
        if not (isinstance(x, dict) and all(x.get(k) for k in ("id", "name", "jobTitle", "url"))):
            err(f"PEOPLE #{i + 1}: საჭიროა id, name, jobTitle, url (მხოლოდ რეალური, ხელშეკრულებით მომუშავე ადამიანი)")
        elif is_placeholder(x["name"]):
            err(f"PEOPLE #{i + 1}: სახელი ფრჩხილებშია — ღია ადგილი პიროვნება არ არის და schema-ში არ შედის")
    members = cfg.get("ORG_MEMBERS")
    if members is not None:
        if not isinstance(members, list):
            err("ORG_MEMBERS უნდა იყოს პიროვნებების id-ების სია, მაგ. [\"person-ani\"]")
        else:
            for mid in members:
                if mid not in people:
                    err(f"ORG_MEMBERS: „{mid}“ უცნობი პიროვნებაა (ცნობილი: {', '.join(people)}) — "
                        "member მხოლოდ რეალური ადამიანია, არასდროს ღია ადგილი")
            if len(set(map(str, members))) != len(members):
                err("ORG_MEMBERS-ში id მეორდება")

    page_status = {p.path: p.status for p in pages}
    for i, svc in enumerate(cfg.get("SERVICES") or []):
        if not (isinstance(svc, dict) and all(svc.get(k) for k in ("id", "name", "path"))):
            err(f"SERVICES #{i + 1}: საჭიროა id, name, path")
            continue
        if svc.get("provider") and svc["provider"] not in people:
            err(f"SERVICES {svc['id']}: provider „{svc['provider']}“ უცნობი პიროვნებაა (ცნობილი: {', '.join(people)})")
        if "ფსიქიატრ" in svc["name"] + str(svc.get("serviceType", "")):
            err(f"SERVICES {svc['id']}: ფსიქიატრის კონსულტაცია სერვისი არ არის (სამედიცინო საქმიანობა) — მხოლოდ მიმართვა")
        if page_status.get(svc["path"]) == "planned":
            err(f"SERVICES {svc['id']}: {svc['path']} status: planned გვერდია — SERVICES მხოლოდ ცოცხალ სერვისებს ჩამოთვლის")

    for i, r in enumerate(cfg.get("REDIRECTS") or []):
        if not valid_redirect(r):
            err(f'REDIRECTS #{i + 1}: ფორმატი ["/dzveli/", "/akhali/", 301] (გზები „/“-ით, კოდი 301 ან 302)')

    opts = cfg.get("ROUTING_OPTIONS")
    if opts is not None:
        known = contact_routing_labels()
        values = []
        for i, o in enumerate(opts if isinstance(opts, list) else [None]):
            if not (isinstance(o, dict) and isinstance(o.get("value"), str) and isinstance(o.get("label"), str)
                    and re.fullmatch(r"[a-z0-9-]{1,40}", o["value"]) and 0 < len(o["label"]) <= 100):
                err(f'ROUTING_OPTIONS #{i + 1}: ფორმატი {{"value": "molodini-tsqvilebi", "label": "… (≤ 100 სიმბოლო)"}}')
                continue
            values.append(o["value"])
            if known is None:
                err(f"ROUTING_OPTIONS: {rel(CONTACT_FUNCTION)}-ში ROUTING_LABELS ვერ მოიძებნა")
                known = {}
            elif known and known.get(o["value"]) != o["label"]:
                err(f"ROUTING_OPTIONS „{o['value']}“: {rel(CONTACT_FUNCTION)}-ის ROUTING_LABELS-ში ეს მნიშვნელობა "
                    f"იგივე ტექსტით უნდა იყოს (ფუნქცია მხოლოდ დაშვებულ მნიშვნელობებს იღებს)")
        if len(set(values)) != len(values):
            err("ROUTING_OPTIONS-ში value მეორდება")
        if not any("{{ROUTING_FIELD}}" in f.read_text(encoding="utf-8") for f in PARTIALS_DIR.glob("*.html")):
            report.add("WARN", where, "ROUTING_OPTIONS არის, მაგრამ არცერთ partial-ში {{ROUTING_FIELD}} არ ჩანს")


def check_fragments(pages: list[Page], cfg: dict, report: Report) -> None:
    """#ანკორიანი ბმულები (მაგ. /pirveli-sesia/#ramdeni-sesia) — სამიზნე id უნდა არსებობდეს (მხოლოდ სრულ აგებაზე)."""
    ids = {p.path: set(re.findall(r'\bid="([^"]+)"', p.html)) for p in pages}
    site = cfg["SITE_URL"]
    for p in pages:
        for href in sorted(set(re.findall(r'href="([^"]*#[^"]+)"', p.html))):
            base, frag = href.split("#", 1)
            base = base.removeprefix(site) or p.path
            if base.startswith("/") and base in ids and frag not in ids[base]:
                report.add("ERROR", p.rel, f"ანკორი არ არსებობს: {href}")


# ---------------------------------------------------------------- site files
def write_site_files(pages: list[Page], cfg: dict, demo: bool = False) -> None:
    site = cfg["SITE_URL"]
    idx = sorted((p for p in pages if p.indexable), key=lambda p: (p.path != "/", p.path))
    write_headers(cfg, demo)
    write_feed(cfg)
    write_redirects(cfg)
    if demo:
        # დემო: საძიებო სისტემებისთვის სრულად დახურული; sitemap.xml და llms.txt არ იწერება
        (DIST / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
        return

    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for p in idx:
        lines.append("  <url>")
        lines.append(f"    <loc>{html.escape(site + p.path)}</loc>")
        lines.append(f"    <lastmod>{p.meta['dateModified']}</lastmod>")
        if p.meta.get("priority") is not None:
            lines.append(f"    <priority>{float(p.meta['priority']):.1f}</priority>")
        lines.append("  </url>")
    lines.append("</urlset>")
    (DIST / "sitemap.xml").write_text("\n".join(lines) + "\n", encoding="utf-8")

    robots = f"""# robots.txt — {urlsplit(site).netloc}
# ყველა საძიებო სისტემას (მათ შორის Googlebot-ს) სრული წვდომა აქვს:
# Google-ის AI Overview Googlebot-ის ინდექსიდან იკვებება — Googlebot-ს არასდროს ვბლოკავთ.
User-agent: *
Allow: /
Disallow: /api/

# AI-ბოტები დაშვებულია. ეს ცალკე გადაწყვეტილებაა (კონცეფცია §11.1): ChatGPT-სა და
# Perplexity-ში ციტირებისთვის. დასაბლოკად შესაბამის ბლოკში „Allow: /“ შეცვალეთ „Disallow: /“-ით.
User-agent: GPTBot
Allow: /
Disallow: /api/

User-agent: ClaudeBot
Allow: /
Disallow: /api/

User-agent: PerplexityBot
Allow: /
Disallow: /api/

Sitemap: {site}/sitemap.xml
"""
    (DIST / "robots.txt").write_text(robots, encoding="utf-8")

    facts = [
        f"- სახელი: {cfg['NAME']} ({cfg['NAME_LATIN']}), {cfg['ROLE']}",
        f"- მისამართი: {cfg['ADDRESS']} ({cfg['DISTRICT']}); სესიები ასევე ონლაინ",
        f"- სესიის ხანგრძლივობა: {cfg['SESSION_MIN']} წუთი",
        f"- {cfg['NAME'].split()[0]} ფსიქოლოგია, არა ფსიქიატრი — მედიკამენტებს არ ნიშნავს",
        "- მიდგომა: გეშტალტთერაპია და სხეულზე ორიენტირებული ფსიქოთერაპია",
        "- ენა: ქართული",
    ]
    if not is_placeholder(cfg.get("PRICE")):
        # PRICE_SAME_ONLINE: false, როცა ონლაინ ფასის თანაბრობა დადასტურებული არ არის (site 3)
        same = " (კაბინეტში და ონლაინ ერთნაირად)" if cfg.get("PRICE_SAME_ONLINE", True) is True else " (კაბინეტში)"
        facts.insert(3, f"- სესიის ფასი: {cfg['PRICE']}{same}")
    if not is_placeholder(cfg.get("HOURS")):
        facts.append(f"- სამუშაო საათები: {cfg['HOURS']}")
    main_pages = [p for p in idx if not p.path.startswith("/blogi/") or p.path == "/blogi/"]
    blog = [p for p in idx if p.path.startswith("/blogi/") and p.path != "/blogi/"]
    out = [f"# {cfg['SITE_NAME']}", "", f"> {cfg['SITE_DESCRIPTION']}", "",
           "საიტი მხოლოდ ქართულ ენაზეა. ძირითადი ფაქტები:", "", *facts, "", "## გვერდები", ""]
    def entry(p: Page) -> str:
        # ფრჩხილებიანი ადგილის შემცველი წინადადებები llms.txt-ში არ გადის
        desc = " ".join(s for s in re.split(r"(?<=\.)\s+", p.meta["_description"]) if not is_placeholder(s))
        return f"- [{p.meta['_title']}]({site}{p.path}): {desc}"

    out += [entry(p) for p in main_pages]
    if blog:
        out += ["", "## ბლოგი", ""]
        out += [entry(p) for p in blog]
    (DIST / "llms.txt").write_text("\n".join(out) + "\n", encoding="utf-8")


def csp_with_style_hashes(csp: str, demo: bool = False) -> str:
    """ჩაშენებული <style>/<script> ბლოკების (შრიფტები, დემო-ზოლი, დემოს პალიტრა) sha256 → CSP style-src/script-src.
    დემოში frame-ancestors 'self' — ფერების შედარების გვერდი საიტებს iframe-ში აჩვენებს."""
    parts = [d.strip() for d in csp.split(";") if d.strip()]
    for directive, hashes in (("style-src", INLINE_STYLE_HASHES), ("script-src", INLINE_SCRIPT_HASHES)):
        if not hashes:
            continue
        extra = " ".join(f"'sha256-{h}'" for h in dict.fromkeys(hashes))
        for i, d in enumerate(parts):
            if d.split()[0] == directive:
                parts[i] = f"{d} {extra}"
                break
        else:
            parts.append(f"{directive} 'self' {extra}")
    if demo:
        parts = [("frame-ancestors 'self'" if d.split()[0] == "frame-ancestors" else d) for d in parts]
    return "; ".join(parts)


def write_headers(cfg: dict, demo: bool = False) -> None:
    headers = f"""/*
  X-Content-Type-Options: nosniff
  X-Frame-Options: {"SAMEORIGIN" if demo else "DENY"}
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=(), usb=()
  Strict-Transport-Security: max-age=31536000
  Cross-Origin-Opener-Policy: same-origin
  Content-Security-Policy: {csp_with_style_hashes(cfg['CSP'], demo)}

/assets/css/*
  Cache-Control: public, max-age=31536000, immutable

/assets/js/*
  Cache-Control: public, max-age=31536000, immutable

/assets/fonts/*
  Cache-Control: public, max-age=31536000, immutable

/assets/img/*
  Cache-Control: public, max-age=2592000, stale-while-revalidate=86400

/sitemap.xml
  Cache-Control: public, max-age=3600

/feed.xml
  Content-Type: application/rss+xml; charset=utf-8
  Cache-Control: public, max-age=3600

/llms.txt
  Content-Type: text/plain; charset=utf-8
"""
    (DIST / "_headers").write_text(headers, encoding="utf-8")


def write_redirects(cfg: dict | None = None) -> None:
    """_redirects. კონფიგის REDIRECTS ([[from, to, code], …]; საიტი 4) ემატება ბოლოს — მის გარეშე ფაილი უცვლელია."""
    redirects = """# Cloudflare Pages _redirects — ამჟამად ცარიელია.
# www → apex საჭირო არ არის (Cloudflare-ის დომენის პარამეტრებში წყდება).
# მაგალითი (ჩასართავად მოაშორეთ „#“):
# /dzveli-misamarti/  /akhali-misamarti/  301
"""
    rules = [r for r in (cfg or {}).get("REDIRECTS") or [] if valid_redirect(r)]
    if rules:
        redirects = redirects.replace("ამჟამად ცარიელია.", "წყარო: site.config.json → REDIRECTS.")
        redirects += "".join(f"{BASE_PATH}{a}  {BASE_PATH}{b}  {int(c)}\n" for a, b, c in rules)
    (DIST / "_redirects").write_text(redirects, encoding="utf-8")


def valid_redirect(r) -> bool:
    return (isinstance(r, list) and len(r) == 3 and all(isinstance(x, str) and x.startswith("/") and " " not in x
            for x in r[:2]) and r[2] in (301, 302))


def write_feed(cfg: dict) -> None:
    """RSS 2.0 ბლოგისთვის (კონცეფცია §8.10, §11.1): /blogi/-ის ყველა type: Article გვერდი, ახლიდან ძველისკენ."""
    from email.utils import format_datetime
    from datetime import datetime, timezone
    site = cfg["SITE_URL"]
    esc = html.escape

    def rfc822(iso: str) -> str:
        d = date.fromisoformat(iso)
        return format_datetime(datetime(d.year, d.month, d.day, 9, 0, tzinfo=timezone.utc))

    items = sorted(ARTICLES, key=lambda a: (a.meta["datePublished"], a.path), reverse=True)
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
           "<channel>",
           f"  <title>{esc(cfg['NAME'])} — ბლოგი</title>",
           f"  <link>{site}/blogi/</link>",
           f'  <atom:link href="{site}/feed.xml" rel="self" type="application/rss+xml"/>',
           f"  <description>{esc(cfg['SITE_DESCRIPTION'])}</description>",
           "  <language>ka</language>"]
    if items:
        out.append(f"  <lastBuildDate>{rfc822(max(a.meta['dateModified'] for a in items))}</lastBuildDate>")
    for a in items:
        link = site + a.path
        out += ["  <item>",
                f"    <title>{esc(a.meta['_h1'])}</title>",
                f"    <link>{link}</link>",
                f'    <guid isPermaLink="true">{link}</guid>',
                f"    <pubDate>{rfc822(a.meta['datePublished'])}</pubDate>",
                f"    <description>{esc(a.meta['_description'])}</description>",
                "  </item>"]
    out += ["</channel>", "</rss>"]
    (DIST / "feed.xml").write_text("\n".join(out) + "\n", encoding="utf-8")




# ---------------------------------------------------------------- base path, fonts, demo
URL_ATTR_RE = re.compile(r'(\s(?:href|src|action|poster|content)=")(/(?!/)[^"]*")')
SRCSET_RE = re.compile(r'(\ssrcset=")([^"]*)(")')
STYLE_BLOCK_RE = re.compile(r"(<style\b[^>]*>)(.*?)(</style>)", re.S | re.I)
STYLE_ATTR_RE = re.compile(r'(\sstyle=")([^"]*)(")')
CSS_URL_RE = re.compile(r"""url\(\s*(['"]?)/(?!/)""")
# საიტის მიერ შექმნილი საქაღალდეები, რომლებსაც --out არასდროს წაშლის
PROTECTED_DIRS = {"sites", "shared", "demo", "functions", "claudedocs", "src", "assets", ".git", ".github"}


def css_with_base(css: str, base: str) -> str:
    """CSS-ში url(/…) → url(<ბაზა>/…)."""
    return CSS_URL_RE.sub(lambda m: f"url({m.group(1)}{base}/", css) if base else css


def apply_base(doc: str, base: str) -> str:
    """root-relative URL-ებს („/…“, არა „//…“) ბაზის გზას უმატებს: href/src/action/poster/content, srcset,
    <style> და style="" (url()). hidden ველის value (PAGE_PATH) და აბსოლუტური URL-ები არ იცვლება."""
    if not base:
        return doc

    def srcset(m: re.Match) -> str:
        parts = []
        for part in m.group(2).split(","):
            url = part.strip()
            if url.startswith("/") and not url.startswith("//"):
                part = part.replace(url, base + url, 1)
            parts.append(part)
        return m.group(1) + ",".join(parts) + m.group(3)

    doc = URL_ATTR_RE.sub(lambda m: m.group(1) + base + m.group(2), doc)
    doc = SRCSET_RE.sub(srcset, doc)
    doc = STYLE_BLOCK_RE.sub(lambda m: m.group(1) + css_with_base(m.group(2), base) + m.group(3), doc)
    return STYLE_ATTR_RE.sub(lambda m: m.group(1) + css_with_base(m.group(2), base) + m.group(3), doc)


def sha256_b64(text: str) -> str:
    return base64.b64encode(hashlib.sha256(text.encode("utf-8")).digest()).decode("ascii")


def fonts_css_text() -> str:
    """shared/fonts.css შეკუმშული (ერთი ხაზი, კომენტარების გარეშე); ცარიელი, თუ შრიფტები არ არის."""
    if not FONTS_CSS_FILE.is_file() or not any(SHARED_FONTS_DIR.glob("*.woff2")):
        return ""
    css = re.sub(r"/\*.*?\*/", "", FONTS_CSS_FILE.read_text(encoding="utf-8"), flags=re.S)
    css = re.sub(r"\s*([{};:,])\s*", r"\1", re.sub(r"\s+", " ", css))
    return css.replace(";}", "}").strip()


def copy_fonts(target: Path) -> None:
    fonts = sorted(SHARED_FONTS_DIR.glob("*.woff2"))
    if fonts:
        target.mkdir(parents=True, exist_ok=True)
        for f in fonts:
            shutil.copy2(f, target / f.name)


def copy_assets() -> None:
    target = DIST / "assets"
    if not ASSETS_DIR.is_dir():
        copy_fonts(target / "fonts")
        return
    shutil.copytree(ASSETS_DIR, target, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns(".DS_Store", "*.tmp"))
    copy_fonts(target / "fonts")
    if BASE_PATH:
        for css in target.rglob("*.css"):
            css.write_text(css_with_base(css.read_text(encoding="utf-8"), BASE_PATH), encoding="utf-8")


# დემო-ზოლი: საიტის CSS-ისგან დამოუკიდებელი; .site-header{top} — sticky ჰედერი ზოლის ქვეშ არ შევიდეს.
# .demo-pal — ფერების არჩევა (წერტილი = მიმდინარე --accent); .demo-embed (?embed=1) — ზოლის გარეშე (შედარების iframe-ები);
# .demo-svg — პალიტრის ჩართვისას SVG-ფოტო ფერის შეცვლამდე არ ჩანს (თავდაპირველი ფერები არ „გაკრთეს“).
DEMO_BAR_CSS = (
    ".demo-bar{position:fixed;top:0;left:0;right:0;z-index:1000;box-sizing:border-box;height:36px;"
    "display:flex;align-items:center;gap:.5em;padding:0 16px;overflow-x:auto;white-space:nowrap;"
    "background:#1F1D1B;color:#FBF8F3;font:400 14px/1.2 \"Noto Sans Georgian\",system-ui,sans-serif}"
    ".demo-bar a{padding:5px 0;color:#FBF8F3;text-decoration:underline;text-underline-offset:3px}"
    ".demo-bar a:focus-visible{outline:2px solid #FBF8F3;outline-offset:2px}"
    ".demo-bar strong{font-weight:700}"
    ".demo-pal{display:inline-flex;align-items:center;gap:.4em;margin-left:.4em;padding-left:.8em;border-left:1px solid #6E6862}"
    ".demo-pal__dot{flex:none;width:12px;height:12px;border-radius:50%;background:var(--accent,#7C2C4C);box-shadow:0 0 0 2px #FBF8F3}"
    ".demo-bar select{font:inherit;color:#FBF8F3;background:#2F2C29;border:1px solid #8A837B;border-radius:4px;"
    "height:26px;padding:0 2px;max-width:12em;color-scheme:dark;cursor:pointer}"
    ".demo-bar select:focus-visible{outline:2px solid #FBF8F3;outline-offset:1px}"
    ".demo-bar__cmp{margin-left:.4em}"
    "@media (min-width:640px){.demo-bar{justify-content:center}}"
    # ზოლი ყოველთვის ერთ ხაზშია (ოთხი საიტით გაზომილი 320/360/390/414/768/1024px): <960px — „დემო ·“ იმალება,
    # საიტის სახელი და „ვარიანტი“ — მხოლოდ ვიზუალურად (ეკრანის მკითხველისთვის რჩება); ნომრის ბმულს 3px შიდა დაშორება
    # (შეხების სამიზნეების ცენტრები ≥24px-ით დაშორებულია — ამიტომ gap არ მცირდება); <520px — „ფერები“ (label)
    # და ფერის წერტილი იმალება, გვერდითი დაშორება 8px; <390px — „შედარება“ იმალება. select-ის სიგანე ისეა შერჩეული,
    # რომ ნაგულისხმევი „საიტის ფერები“ (≈130px) ყველა სიგანეზე ბოლომდე ჩანდეს.
    "@media (max-width:959px){.demo-bar{gap:.3em;padding:0 12px;font-size:13px}.demo-bar__lbl{display:none}"
    ".demo-bar__n,.demo-bar__more{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}"
    ".demo-bar select{max-width:10.5em}.demo-bar .demo-bar__site{padding-inline:3px}}"
    "@media (max-width:519px){.demo-pal label{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}"
    ".demo-bar{padding:0 8px}.demo-bar select{max-width:10.5em}.demo-pal__dot{display:none}}"
    "@media (max-width:389px){.demo-bar__cmp{display:none}}"
    # საიტის skip-link (top:.5rem) ფიქსირებული ზოლის ქვეშ არ მოექცეს
    "body{padding-top:36px}.site-header{top:36px}html:not(.demo-embed) .skip-link:focus{top:calc(36px + .5rem)}"
    "html.demo-embed body{padding-top:0}.demo-embed .demo-bar{display:none}.demo-embed .site-header{top:0}"
    ".demo-svg img[src*=\"/assets/img/\"][src$=\".svg\"]{opacity:0}"
)

def demo_bar_css(site_dir: Path) -> str:
    """DEMO_BAR_CSS + საიტის scroll-padding-top-ს ემატება ზოლის 36px (#ანკორები sticky ჰედერის ქვეშ არ მოექცეს)."""
    css_file = site_dir / "assets" / "css" / "style.css"
    css = css_file.read_text(encoding="utf-8") if css_file.is_file() else ""
    m = re.search(r"scroll-padding-top\s*:\s*([^;}]+)", css)
    pad = m.group(1).strip() if m else "0px"
    return DEMO_BAR_CSS + f"html:not(.demo-embed){{scroll-padding-top:calc({pad} + 36px)}}"


# დემოს პალიტრა (<head>-ში, სინქრონულად — ორიგინალი ფერები არ „გაკრთება“). __P__ = {id: [10 ტოკენი „#“-ის გარეშე…
# (+ --line მყარი ფერი, თუ საიტის SVG-ები მას იყენებს)]},
# __K__ = ტოკენების სახელები, __M__ = საიტის :root-ის hex → ტოკენის ინდექსი (SVG-ფოტოების გადაფერადებისთვის).
# ?ferebi=<id> — ჩართვა და შენახვა (?embed=1-ით — შენახვის გარეშე); ?ferebi= (ცარიელი) — საიტის ფერები; უცნობი id — იგნორი.
# CSS ჩაისმება CSSOM-ით (insertRule) ცარიელ <style id="demo-palette-css">-ში — CSP-ს ჰეშიც ცარიელი ბლოკისაა.
PALETTE_JS = (
    '(function(){var P=__P__,K=__K__,M=__M__,N="' + PALETTE_STORAGE_KEY + '",d=document,h=d.documentElement,'
    'q=new URLSearchParams(location.search),E=q.get("embed")=="1",u=q.get("ferebi"),c="",F={},T,W=1;'
    'function G(){try{return localStorage.getItem(N)||""}catch(x){W=0;return""}}'
    'function S(v){if(!E)try{v?localStorage.setItem(N,v):localStorage.removeItem(N)}catch(x){W=0}}'
    # URL-ის ?ferebi არჩევანს მიჰყვება (თორემ განახლება ძველ ფერს დააბრუნებს); შენახვის გარეშე — ერთადერთი მეხსიერება
    'function U(){if(E||W&&!q.has("ferebi"))return;c?q.set("ferebi",c):q.delete("ferebi");var s=q.toString();'
    'history.replaceState(history.state,"",location.pathname+(s?"?"+s:"")+location.hash)}'
    'function A(v){var s=d.getElementById("demo-palette-css").sheet,p;c=P[v]?v:"";p=P[c];'
    'while(s.cssRules.length)s.deleteRule(0);'
    'if(p)s.insertRule("html:root{"+K.map(function(k,i){return"--"+k+":#"+p[i]}).join(";")'
    '+";--line:color-mix(in srgb,var(--ink) 14%,transparent);--placeholder:var(--ink-soft)}",0);'
    'h.classList.toggle("demo-svg",!!p);if(d.body)I()}'
    'function I(){var m=d.querySelector(\'meta[name="theme-color"]\'),e=d.getElementById("demo-palette"),p=c;'
    'if(m){if(T==null)T=m.content;m.content=p?"#"+P[p][0]:T}if(e)e.value=p;'
    'd.querySelectorAll("img").forEach(function(g){var o=g.getAttribute("data-demo-src")||g.getAttribute("src")||"";'
    'if(!/\\/assets\\/img\\/[^?#]+\\.svg([?#]|$)/.test(o))return;g.setAttribute("data-demo-src",o);'
    'if(!p){if(g.getAttribute("src")!=o)g.setAttribute("src",o);return}'
    '(F[o]=F[o]||fetch(o).then(function(r){if(!r.ok)throw r;return r.text()})).then(function(t){'
    'if(p==c)g.src="data:image/svg+xml;charset=utf-8,"+encodeURIComponent(t.replace(/#[0-9a-f]{6}\\b/gi,'
    'function(x){var i=M[x.toUpperCase()];return i==null?x:"#"+P[p][i]}))},function(){h.classList.remove("demo-svg")})})}'
    'if(u!=null&&(u==""||P[u])){A(u);S(c)}else A(G());if(E)h.classList.add("demo-embed");'
    'd.addEventListener("DOMContentLoaded",function(){var e=d.getElementById("demo-palette");I();'
    'if(e)e.onchange=function(){A(e.value);S(c);U()};'
    # embed-ში (და როცა localStorage მიუწვდომელია) ფერი შიდა ბმულებით გადადის
    'd.addEventListener("click",function(v){var a=v.target.closest&&v.target.closest("a[href]"),s;'
    'if(a&&(E||!W&&c)&&a.origin==location.origin&&a.pathname!=location.pathname){s=new URLSearchParams(a.search);'
    's.set("ferebi",c);if(E)s.set("embed","1");a.search=s}},!0)});'
    'addEventListener("pageshow",function(v){if(v.persisted&&!E&&W){A(G());U()}});'
    'addEventListener("storage",function(v){if(v.key==N&&!E){A(v.newValue||"");U()}})})();'
)
HEX6_RE = re.compile(r"#[0-9A-Fa-f]{6}")
_PALETTES_CACHE: list[dict] | None = None


def load_palettes() -> list[dict]:
    """demo/palettes.json → სწორი პალიტრების სია (არასწორი ჩანაწერი WARN-ით გამოტოვდება; ფაილის გარეშე — [])."""
    global _PALETTES_CACHE
    if _PALETTES_CACHE is not None:
        return _PALETTES_CACHE
    _PALETTES_CACHE = []
    if not PALETTES_FILE.is_file():
        return _PALETTES_CACHE
    try:
        data = json.loads(PALETTES_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"WARN  demo/palettes.json: JSON შეცდომა — {e}")
        return _PALETTES_CACHE
    seen = set()
    for i, p in enumerate(data if isinstance(data, list) else []):
        colors = p.get("colors") if isinstance(p, dict) else None
        pid = str(p.get("id", "")) if isinstance(p, dict) else ""
        bad = [t for t in PALETTE_TOKENS if not (isinstance(colors, dict) and HEX6_RE.fullmatch(str(colors.get(t, ""))))]
        if not re.fullmatch(r"[a-z0-9-]+", pid) or pid in seen or not p.get("name") or bad:
            print(f"WARN  demo/palettes.json #{i + 1} ({pid or '?'}): გამოტოვებულია (id/name/ფერები: {', '.join(bad) or 'id'})")
            continue
        seen.add(pid)
        _PALETTES_CACHE.append(p)
    return _PALETTES_CACHE


def root_colors(site_dir: Path) -> dict[str, str]:
    """საიტის style.css-ის პირველი :root ბლოკის hex ცვლადები: {"paper": "#F5F3EB", …}."""
    css_file = site_dir / "assets" / "css" / "style.css"
    css = css_file.read_text(encoding="utf-8") if css_file.is_file() else ""
    m = re.search(r":root\s*\{(.*?)\}", css, re.S)
    return {k: v.upper() for k, v in re.findall(r"--([\w-]+)\s*:\s*(#[0-9A-Fa-f]{6})\b", m.group(1) if m else "")}


def hex_over(fg: str, bg: str, alpha: float) -> str:
    """fg ფერი alpha გამჭვირვალობით bg-ზე → მყარი hex (SVG-ში --line-ის ნაცვლად)."""
    f, b = (tuple(int(c[i:i + 2], 16) for i in (1, 3, 5)) for c in (fg, bg))
    return "#" + "".join(f"{round(x * alpha + y * (1 - alpha)):02X}" for x, y in zip(f, b))


def palette_script(site_dir: Path, palettes: list[dict]) -> str:
    idx = {t: i for i, t in enumerate(PALETTE_TOKENS)}
    idx["line"] = len(PALETTE_TOKENS)
    hex_map: dict[str, int] = {}
    for tok, val in root_colors(site_dir).items():
        if tok in idx:
            hex_map.setdefault(val, idx[tok])
    line = idx["line"] in hex_map.values()  # მყარი --line მხოლოდ მაშინ, როცა საიტის :root-ში --line hex-ია (საიტი 2)
    data = {p["id"]: [p["colors"][t].upper()[1:] for t in PALETTE_TOKENS]
            + ([hex_over(p["colors"]["ink"], p["colors"]["paper"], .14)[1:]] if line else []) for p in palettes}
    dump = lambda o: json.dumps(o, separators=(",", ":"))  # noqa: E731
    return (PALETTE_JS.replace("__P__", dump(data)).replace("__K__", dump(PALETTE_TOKENS))
            .replace("__M__", dump(hex_map)))


def demo_bar(slug: str, page_path: str, all_root: str, site_paths: dict[str, set[str]] | None,
             palettes: list[dict] | None = None) -> str:
    """დემო-ზოლი. site_paths (--all) — ყველა აგებული საიტის გვერდები: ბმული იმავე გვერდზე, თუ ის საიტს აქვს,
    სხვაგვარად საიტის მთავარზე. site_paths=None (ერთი საიტი) — ბმულები მთავარ გვერდებზე.
    palettes — ფერების <select> (და --all-ში ბმული შედარების გვერდზე)."""
    esc = html.escape
    items = []
    if slug not in {d["slug"] for d in DEMO_SITES}:
        items.append(f"<strong>{esc(slug)}</strong>")
    for d in DEMO_SITES:
        num, _, name = d["bar"].partition(" ")
        label = esc(num) + (f'<span class="demo-bar__n"> {esc(name)}</span>' if name else "")
        if d["slug"] == slug:
            items.append(f'<strong aria-current="true">{label}</strong>')
            continue
        if site_paths is not None and d["slug"] not in site_paths:
            continue  # --all: ეს საიტი ჯერ არ არსებობს
        same = site_paths is not None and page_path in site_paths[d["slug"]] and not page_path.endswith(".html")
        items.append(f'<a class="demo-bar__site" href="{all_root}/{d["slug"]}{page_path if same else "/"}">{label}</a>')
    items.append(f'<a href="{all_root}/">ყველა<span class="demo-bar__more"> ვარიანტი</span></a>')
    bar = ('<div class="demo-bar" role="navigation" aria-label="დემო-ვარიანტები"><span class="demo-bar__lbl">დემო ·</span> '
           + " · ".join(items))
    if palettes:
        opts = "".join(f'<option value="{esc(p["id"])}">{esc(p["name"])}</option>' for p in palettes)
        bar += ('<span class="demo-pal"><span class="demo-pal__dot" aria-hidden="true"></span>'
                '<label for="demo-palette">ფერები</label><select id="demo-palette" autocomplete="off">'
                f'<option value="">საიტის ფერები</option>{opts}</select></span>')
        if site_paths is not None:
            cmp = next((d for d in DEMO_SITES if d["slug"] == slug), None)
            query = f"?saiti={slug}" if cmp else ""
            if cmp and page_path in {p for p, _ in cmp["compare"]}:
                query += f"&amp;gverdi={page_path}"
            bar += f'<a class="demo-bar__cmp" href="{all_root}/ferebi/{query}">შედარება</a>'
    return bar + "</div>"


def inject_demo(doc: str, bar: str, palette_head: str = "", bar_css: str = DEMO_BAR_CSS) -> str:
    """ვალიდაციის შემდეგ: დემო-ზოლი <body>-ის შემდეგ, მისი <style> (და პალიტრის <style>/<script>) </head>-მდე,
    ფორმებზე data-demo="1"."""
    doc = re.sub(r"<form\b(?=[^>]*\bdata-ajax\b)", '<form data-demo="1"', doc)
    # შეუვსებელი ბმული (href="[…]") დემოში 404-ზე არ გადავიდეს: href="#", ახალი ჩანართის გარეშე
    doc = re.sub(r'<a\b[^>]*\shref="\[[^"\]]*\]"[^>]*>',
                 lambda m: re.sub(r'\s(?:target|rel)="[^"]*"', "",
                                  re.sub(r'\shref="\[([^"\]]*)\]"', r' href="#" title="\1"', m.group(0))), doc)
    doc = doc.replace("</head>", f"<style>{bar_css}</style>\n{palette_head}</head>", 1)
    return re.sub(r"(<body\b[^>]*>)", lambda m: m.group(1) + "\n" + bar, doc, count=1)


def site_page_paths(site_dir: Path) -> set[str]:
    """საიტის ყველა გვერდის meta.path (მხოლოდ meta ბლოკიდან, აგების გარეშე)."""
    paths = set()
    for f in (site_dir / "src" / "pages").rglob("*.html"):
        m = META_RE.match(f.read_text(encoding="utf-8"))
        if m:
            try:
                paths.add(json.loads(m.group(1)).get("path", ""))
            except json.JSONDecodeError:
                pass
    return paths


def write_chooser(out: Path, base_path: str, built: set[str], demo: bool = False) -> None:
    """--all: <out>/index.html (ვარიანტების არჩევა) და <out>/404.html — demo/ შაბლონებიდან;
    --demo-ში პალიტრებით — ასევე <out>/ferebi/index.html (ფერების შედარება)."""
    esc = html.escape
    cards = []
    for d in DEMO_SITES:
        slug, label = d["slug"], esc(d["label"])
        href = f"{base_path}/{slug}/"
        if slug not in built:
            cards.append(f'<li class="variant is-pending">\n  <span class="variant__media" aria-hidden="true"></span>\n'
                         f'  <div class="variant__body">\n    <h2 class="variant__title">{label}</h2>\n'
                         f'    <p>{esc(d["blurb"])}</p>\n    <p class="variant__soon">ვარიანტი მზადდება</p>\n  </div>\n</li>')
            continue
        if (SITES_DIR / slug / "assets" / "img" / "og-default.png").is_file():
            img = (f'<img src="{href}assets/img/og-default.png" alt="" width="1200" height="630" '
                   f'decoding="async">')  # lazy-ის გარეშე: ბარათები (2 × 2) პირველ ეკრანებზეა
        else:
            img = ""
        cards.append(f'<li class="variant">\n  <a class="variant__media" href="{href}" tabindex="-1" aria-hidden="true">{img}</a>\n'
                     f'  <div class="variant__body">\n    <h2 class="variant__title">{label}</h2>\n'
                     f'    <p>{esc(d["blurb"])}</p>\n'
                     f'    <a class="variant__btn" href="{href}" aria-label="ნახვა — {label}">ნახვა</a>\n  </div>\n</li>')
    fonts = fonts_css_text()
    palettes = load_palettes() if demo else []
    tokens = {
        "BASE": base_path,
        "CARDS": "\n".join(cards),
        "FONTS_CSS": f"<style>{css_with_base(fonts, base_path)}</style>" if fonts else "",
        "FEREBI_NOTE": "", "FEREBI_BLOCK": "",
    }
    if palettes:
        tokens["FEREBI_NOTE"] = '<p class="note">ფერების შეცვლა ნებისმიერ გვერდზე შეგიძლიათ — ზედა ზოლში, „ფერები“.</p>'
        tokens["FEREBI_BLOCK"] = (
            '<section class="compare" aria-labelledby="compare-title">\n'
            '    <h2 id="compare-title" class="compare__title">ფერების შედარება — ნებისმიერი ვარიანტი ნებისმიერ ფერში</h2>\n'
            f'    <p>ერთ ეკრანზე ნახავთ, როგორ გამოიყურება არჩეული გვერდი {len(palettes)} სხვადასხვა ფერში.</p>\n'
            f'    <a class="variant__btn" href="{base_path}/ferebi/">ფერების შედარება</a>\n'
            '  </section>')
        write_compare_page(out, base_path, built, palettes, fonts)
    for name in ("index.html", "404.html"):
        doc = COMMENT_RE.sub("", (DEMO_DIR / name).read_text(encoding="utf-8")).lstrip()
        doc = TOKEN_RE.sub(lambda m: tokens.get(m.group(1), m.group(0)), doc)
        left = sorted(set(TOKEN_RE.findall(doc)))
        if left:
            print(f"WARN  demo/{name}: გადაუწყვეტელი ტოკენები: {', '.join(left)}")
        (out / name).write_text(doc, encoding="utf-8")
    copy_fonts(out / "assets" / "fonts")
    (out / ".nojekyll").write_text("", encoding="utf-8")


def write_compare_page(out: Path, base_path: str, built: set[str], palettes: list[dict], fonts: str) -> None:
    """--all --demo: <out>/ferebi/index.html — ერთი გვერდი ყველა პალიტრაში (demo/ferebi.html შაბლონიდან)."""
    sites = []
    for d in DEMO_SITES:
        if d["slug"] not in built:
            continue
        paths = site_page_paths(SITES_DIR / d["slug"])
        pages = [[path, label] for path, label in d["compare"] if path in paths]
        missing = [path for path, _ in d["compare"] if path not in paths]
        if missing:
            print(f"WARN  ფერების შედარება: {d['slug']}-ს არ აქვს {', '.join(missing)}")
        colors = root_colors(SITES_DIR / d["slug"])
        sites.append({"slug": d["slug"], "label": d["label"], "pages": pages,
                      "colors": {t: colors[t] for t in PALETTE_TOKENS if t in colors}})
    data = {"base": base_path, "key": PALETTE_STORAGE_KEY, "tokens": PALETTE_TOKENS, "sites": sites,
            "palettes": [{"id": p["id"], "name": p["name"], "note": p.get("note", ""),
                          "colors": {t: p["colors"][t].upper() for t in PALETTE_TOKENS}} for p in palettes]}
    tokens = {
        "BASE": base_path,
        "FONTS_CSS": f"<style>{css_with_base(fonts, base_path)}</style>" if fonts else "",
        "DATA": json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"),
    }
    doc = COMMENT_RE.sub("", (DEMO_DIR / "ferebi.html").read_text(encoding="utf-8")).lstrip()
    doc = TOKEN_RE.sub(lambda m: tokens.get(m.group(1), m.group(0)), doc)
    left = sorted(set(TOKEN_RE.findall(doc)))
    if left:
        print(f"WARN  demo/ferebi.html: გადაუწყვეტელი ტოკენები: {', '.join(left)}")
    (out / "ferebi").mkdir(parents=True, exist_ok=True)
    (out / "ferebi" / "index.html").write_text(doc, encoding="utf-8")


# ---------------------------------------------------------------- placeholders report
PHONE_PLACEHOLDER = "ტელეფონის ნომერი (995XXXXXXXXX: tel/WhatsApp)"


def write_placeholders_report(path: Path, results: list[tuple[Path, dict, list[Page]]]) -> None:
    """ქართული markdown ცხრილი: ადგილი · კონფიგის გასაღები · ფაილები · რაოდენობა (აგებული გვერდებიდან)."""
    lines = ["# შესავსები ადგილები", "",
             f"გენერირებულია `python3 build.py --placeholders-report` ბრძანებით, {date.today().isoformat()}. "
             "ხელით არ შეცვალოთ — ხელახლა დააგენერირეთ. ფაილები = გვერდის წყარო (`src/pages/…`); "
             "„რაოდენობა“ = რამდენჯერ ჩანს აგებულ გვერდებზე (ტექსტი + ატრიბუტები).", ""]
    for site_dir, cfg, pages in results:
        pages_dir = site_dir / "src" / "pages"
        by_ph: dict[str, Counter] = {}
        for p in pages:
            for ph, n in p.placeholders.items():
                by_ph.setdefault(ph, Counter())[str(p.src.resolve().relative_to(pages_dir))] += n
        cfg_keys: dict[str, list[str]] = {}
        for key, val in cfg.items():
            if key.startswith("_") or not isinstance(val, str):
                continue
            for ph in dict.fromkeys(PLACEHOLDER_RE.findall(val)):
                cfg_keys.setdefault(ph, []).append(key)
            if "XXXX" in val:
                cfg_keys.setdefault(PHONE_PLACEHOLDER, []).append(key)
        for ph in cfg_keys:
            by_ph.setdefault(ph, Counter())
        lines += [f"## {rel(site_dir)}", "", f"{len(by_ph)} ადგილი · {len(pages)} გვერდი", "",
                  "| ადგილი | კონფიგის გასაღები | ფაილები | რაოდენობა |", "|---|---|---|---|"]
        for ph in sorted(by_ph, key=lambda x: (-sum(by_ph[x].values()), x)):
            files = by_ph[ph]
            if not files:
                where = "— (გვერდებზე არ ჩანს)"
            elif len(files) == len(pages) > 1:
                where = f"ყველა გვერდი ({len(pages)})"
            else:
                where = ", ".join(f"`{f}`" for f in sorted(files))
            keys = ", ".join(f"`{k}`" for k in cfg_keys.get(ph, [])) or "—"
            cell = ph.replace("|", "\\|")
            lines.append(f"| {cell} | {keys} | {where} | {sum(files.values())} |")
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"შესავსები ადგილების ცხრილი: {rel(path)}")


# ---------------------------------------------------------------- main
def safe_to_clean(out: Path) -> bool:
    """--out იშლება მხოლოდ მაშინ, როცა ROOT-ის შიგნითაა და არ არის წყაროს საქაღალდე."""
    try:
        parts = out.resolve().relative_to(ROOT).parts
    except ValueError:
        return False
    return bool(parts) and parts[0] not in PROTECTED_DIRS


def out_allowed(out: Path) -> bool:
    """--out არ შეიძლება იყოს ROOT, მისი მშობელი ან წყაროს საქაღალდე (sites/, shared/ …) — იქ ჩაწერა წყაროს გადაფარავს."""
    out = out.resolve()
    if out == ROOT or out in ROOT.parents:
        return False
    try:
        parts = out.relative_to(ROOT).parts
    except ValueError:
        return True
    return parts[0] not in PROTECTED_DIRS


def resolve_site(arg: str | None) -> Path:
    if not arg:
        return DEFAULT_SITE
    for cand in (Path.cwd() / arg, ROOT / arg, SITES_DIR / arg):
        if (cand / "site.config.json").is_file():
            return cand.resolve()
    return (Path.cwd() / arg).resolve()


def build_site(site_dir: Path, out: Path, args, *, site_url: str | None = None, clean: bool = True,
               site_paths: dict[str, set[str]] | None = None, all_root: str = "") -> tuple[int, dict, list[Page]]:
    """ერთი საიტის აგება და შემოწმება → (გამოსვლის კოდი, კონფიგი, გვერდები)."""
    global DIST, BASE_PATH
    use_site(site_dir)
    DIST = out
    report = Report()
    if not CONFIG_FILE.is_file():
        print(f"საიტი ვერ მოიძებნა: {rel(CONFIG_FILE)} არ არსებობს")
        return 1, {}, []
    if not LAYOUT_FILE.is_file():
        print(f"ERROR {rel(LAYOUT_FILE)} არ არსებობს — საიტს layout.html სჭირდება (დააკოპირეთ sites/1-brendi/src/-იდან)")
        return 1, {}, []
    cfg = load_config()
    if site_url:
        cfg["SITE_URL"] = site_url
    cfg["SITE_URL"] = cfg["SITE_URL"].rstrip("/")
    BASE_PATH = urlsplit(cfg["SITE_URL"]).path.rstrip("/")
    apply_site_config(cfg)
    base_tokens = config_tokens(cfg)

    INLINE_STYLE_HASHES.clear()
    INLINE_SCRIPT_HASHES.clear()
    fonts_css = fonts_css_text()
    base_tokens["FONTS_CSS"] = f"<style>{fonts_css}</style>" if fonts_css else ""
    if fonts_css:
        INLINE_STYLE_HASHES.append(sha256_b64(css_with_base(fonts_css, BASE_PATH)))
    palettes, palette_head = [], ""
    if args.demo:
        bar_css = demo_bar_css(SITE_DIR)
        INLINE_STYLE_HASHES.append(sha256_b64(bar_css))
        palettes = load_palettes()
        if palettes:  # ფერების გადამრთველი: ცარიელი <style> (CSSOM-ით ივსება) + სკრიპტი, ორივე CSP-ის ჰეშით
            js = palette_script(SITE_DIR, palettes)
            INLINE_STYLE_HASHES.append(sha256_b64(""))
            INLINE_SCRIPT_HASHES.append(sha256_b64(js))
            palette_head = f'<style id="demo-palette-css"></style>\n<script>{js}</script>\n'

    sources = sorted(PAGES_DIR.rglob("*.html"))
    pages = [p for p in (read_page(s, report) for s in sources) if p]
    for p in pages:  # resolved title/description for uniqueness checks
        page_tokens(p, base_tokens)
    for p in pages:  # planned გვერდი < 1 000 სიტყვით: noindex (ARTICLES/sitemap/llms/feed-მდე)
        if p.status == "planned" and not p.meta.get("noindex"):
            words = prose_words(p)
            if words < PLANNED_MIN_WORDS:
                p.meta["noindex"] = True
                report.add("WARN" if args.release else "INFO", p.rel,
                           f"status: planned, .prose-ში {words} სიტყვაა (< {PLANNED_MIN_WORDS}) — გვერდი noindex-ია და "
                           "sitemap/llms.txt/feed-ში არ შედის, სანამ სახელმძღვანელო ტექსტი არ დაიწერება")
    ARTICLES[:] = sorted((p for p in pages if p.meta.get("type") == "Article" and p.indexable
                          and p.path.startswith("/blogi/") and p.path != "/blogi/"),
                         key=lambda p: (p.meta.get("datePublished", ""), p.path))
    for p in pages:  # წაკითხვის დრო ARTICLES-ის შემდეგ: {{PAGE_READING_MIN}} და {{BLOG_CARDS}}
        p.reading_min = reading_minutes(p)
    base_tokens["BLOG_CARDS"] = blog_cards(cfg, report)
    site_checks(pages, cfg, report)

    single = None
    if args.page:
        targets = {(Path.cwd() / args.page).resolve(), (SITE_DIR / args.page).resolve()}
        single = next((p for p in pages if p.src.resolve() in targets), None)
        if not single:
            print(f"გვერდი ვერ მოიძებნა ან meta ბლოკი არასწორია: {args.page}")
            report.print()
            return 1, cfg, pages

    ctx = {
        "site_url": cfg["SITE_URL"],
        "built": {p.path for p in pages},
        "release": args.release,
        "single": bool(single),
        "planned_hits": {},
        "placeholder_links": set(),
    }

    to_build = [single] if single else pages
    if clean and not single and DIST.exists() and safe_to_clean(DIST):
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True, exist_ok=True)

    for p in to_build:
        render(p, cfg, base_tokens, report, demo=args.demo)
        ctx["planned_hits"] = {}
        validate(p, ctx, report)
        for level in LEVELS:
            paths = sorted(k for k, v in ctx["planned_hits"].items() if v == level)
            if paths:
                report.add(level, p.rel, f"ბმულები დაგეგმილ, ჯერ დაუწერელ გვერდებზე ({len(paths)}): {' '.join(paths)}")
        # ვალიდაცია დასრულდა — ახლა ბაზის გზა და (დემოში) დემო-ზოლი
        doc = apply_base(p.html, BASE_PATH)
        if args.demo:
            doc = inject_demo(doc, demo_bar(SITE_DIR.name, p.path, all_root, site_paths, palettes), palette_head,
                              bar_css)
        out_file = output_file(p.path)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(doc, encoding="utf-8")

    copy_assets()
    if not single:
        check_fragments(pages, cfg, report)
        write_site_files(pages, cfg, demo=args.demo)

    if single:
        report.items = [it for it in report.items if it[1] in (single.rel, rel(CONFIG_FILE))
                        or it[0] == "ERROR"]
    report.print()
    built = ", ".join(sorted(rel(output_file(p.path)) for p in to_build))
    print(f"აგებულია: {built}")
    return (1 if report.count("ERROR") else 0), cfg, (to_build if single else pages)


def build_all(args, out: Path) -> int:
    """ყველა sites/*/ → <out>/<slug>/ (SITE_URL = BASE/<slug>) + <out>/index.html და 404.html."""
    site_dirs = sorted(d for d in SITES_DIR.iterdir() if (d / "site.config.json").is_file())
    found = {d.name for d in site_dirs}
    for d in sorted(SITES_DIR.iterdir()):
        if d.is_dir() and not d.name.startswith(".") and d.name not in found:
            print(f"WARN  {rel(d)}: site.config.json არ არის — საიტი გამოტოვებულია")
    for d in DEMO_SITES:
        if d["slug"] not in found and not (SITES_DIR / d["slug"]).is_dir():
            print(f"WARN  sites/{d['slug']} ჯერ არ არსებობს — გამოტოვებულია")
    base_url = (args.site_url or "").rstrip("/")
    base_path = urlsplit(base_url).path.rstrip("/")
    site_paths = {d.name: site_page_paths(d) for d in site_dirs}
    if out.exists() and safe_to_clean(out):
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    code, results = 0, []
    for d in site_dirs:
        if base_url:
            url = f"{base_url}/{d.name}"
        else:  # --site-url-ის გარეშე: საიტის SITE_URL + /<slug> (ლოკალური ნახვა dist-ის ფესვიდან)
            with (d / "site.config.json").open(encoding="utf-8") as fh:
                url = json.load(fh)["SITE_URL"].rstrip("/") + f"/{d.name}"
        print(f"\n========== {rel(d)} → {rel(out / d.name)} ({url})")
        rc, cfg, pages = build_site(d, out / d.name, args, site_url=url, clean=False,
                                    site_paths=site_paths, all_root=base_path)  # root-relative: ჰოსტისგან დამოუკიდებელი
        code = max(code, rc)
        results.append((d.resolve(), cfg, pages))
    write_chooser(out, base_path, found, demo=args.demo)
    print(f"\nარჩევის გვერდი: {rel(out / 'index.html')} · {rel(out / '404.html')}"
          + (f" · ფერები: {rel(out / 'ferebi' / 'index.html')}" if (out / "ferebi" / "index.html").is_file() else ""))
    if args.placeholders_report:
        write_placeholders_report(Path(args.placeholders_report).resolve(), results)
    return code


def main() -> int:
    ap = argparse.ArgumentParser(description="anibarjadze.ge build (მრავალსაიტიანი)")
    ap.add_argument("--site", help="საიტის საქაღალდე (ნაგულისხმევი: sites/1-brendi)")
    ap.add_argument("--all", action="store_true", help="ყველა sites/*/ → <out>/<slug>/ + არჩევის გვერდი")
    ap.add_argument("--out", help="გამოსატანი საქაღალდე (ნაგულისხმევი: dist/ რეპოზიტორიის ფესვში)")
    ap.add_argument("--site-url", help="SITE_URL-ის ჩანაცვლება; path ნაწილი = ბაზის გზა (--all-ში: BASE, საიტი = BASE/<slug>)")
    ap.add_argument("--demo", action="store_true", help="დემო: noindex, Disallow: /, დემო-ზოლი, ფორმა არ იგზავნება")
    ap.add_argument("--page", help="მხოლოდ ერთი გვერდის აგება/შემოწმება, მაგ. src/pages/fasi.html")
    ap.add_argument("--release", action="store_true", help="გაშვებამდე: ფრჩხილებიანი ადგილები = ERROR")
    ap.add_argument("--placeholders-report", metavar="PATH", help="[ფრჩხილების] markdown ცხრილი ამ ფაილში")
    args = ap.parse_args()

    out = Path(args.out).resolve() if args.out else ROOT / "dist"
    if not out_allowed(out):
        print(f"--out {out}: აქ ჩაწერა აკრძალულია (რეპოზიტორიის ფესვი ან წყაროს საქაღალდე). მაგ.: --out dist/<slug>")
        return 2
    if args.all:
        if args.page or args.site:
            print("--all არ ერწყმის --page-ს ან --site-ს")
            return 2
        return build_all(args, out)

    site_dir = resolve_site(args.site)
    all_root = ""
    if args.site_url:  # ერთი საიტი: „ყველა ვარიანტი“ = --site-url-ის მშობელი გზა
        parts = urlsplit(args.site_url.rstrip("/"))
        all_root = f"{parts.scheme}://{parts.netloc}{posixpath.dirname(parts.path)}".rstrip("/")
    code, cfg, pages = build_site(site_dir, out, args, site_url=args.site_url, all_root=all_root)
    if args.placeholders_report and cfg:
        write_placeholders_report(Path(args.placeholders_report).resolve(), [(site_dir, cfg, pages)])
    return code


if __name__ == "__main__":
    sys.exit(main())
