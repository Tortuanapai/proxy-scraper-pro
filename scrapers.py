"""Scrapers V2: GitHub masivo + TXT + JSON + tablas + Google real."""
import json
import re
import time
import urllib.parse
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE = Path(__file__).parent
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36"}

IPPORT = re.compile(r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s*[:\s]\s*(\d{2,5})")


def parse_sources():
    with open(BASE / "sources.json", encoding="utf-8") as f:
        return json.load(f)


def norm_proxy(ip, port, ptype, country="--", anonymity="unknown", source="", username="", password=""):
    try:
        port = int(str(port).strip())
        if not 1 <= port <= 65535:
            return None
    except Exception:
        return None
    ip = str(ip).strip()
    if not re.match(r"^\d{1,3}(\.\d{1,3}){3}$", ip):
        return None
    # filtra 0.0.0.0 y privadas obvias
    if ip.startswith(("0.", "10.", "127.", "192.168.")):
        return None
    return {
        "ip": ip, "port": port,
        "type": str(ptype).upper(),
        "country": (str(country).strip().upper()[:20] if country else "--"),
        "anonymity": str(anonymity).lower(),
        "source": source, "latency": -1,
        "username": (username or "").strip(),
        "password": (password or "").strip(),
    }


# user:pass@ip:port  /  proto://user:pass@ip:port  /  proto://ip:port
AUTH_RE = re.compile(
    r"(?:(https?|socks4|socks5)://)?(?:([^:@/\s]+):([^:@/\s]+)@)?(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d{2,5})",
    re.IGNORECASE,
)
# ip:port:user:pass
AUTH_RE2 = re.compile(
    r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d{2,5}):([^:@\s]+):([^:@\s]+)"
)


def parse_proxy_line(line, default_type="HTTP", source="manual"):
    """Parsea todos los formatos: ip:port, proto://ip:port, user:pass@ip:port, ip:port:user:pass."""
    line = (line or "").strip()
    if not line or line.startswith("#"):
        return None
    # 1. ip:port:user:pass
    m2 = AUTH_RE2.search(line)
    if m2:
        return norm_proxy(m2.group(1), m2.group(2), default_type, source=source,
                          username=m2.group(3), password=m2.group(4))
    # 2. [proto://][user:pass@]ip:port
    m = AUTH_RE.search(line)
    if m:
        proto, user, pwd, ip, port = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
        ptype = proto.upper() if proto else default_type
        # https -> HTTPS
        if ptype == "HTTP" and proto and proto.lower() == "https":
            ptype = "HTTPS"
        return norm_proxy(ip, port, ptype, source=source, username=user or "", password=pwd or "")
    return None


def scrape_text_blob(text, ptype, source):
    """Extrae ip:puerto de cualquier texto (txt, html, json crudo), con y sin auth."""
    out = []
    seen = set()
    # primero formatos con auth ip:port:user:pass
    for m in AUTH_RE2.finditer(text):
        px = norm_proxy(m.group(1), m.group(2), ptype, source=source,
                        username=m.group(3), password=m.group(4))
        if px:
            k = (px["ip"], px["port"], px.get("username", ""))
            if k not in seen:
                seen.add(k)
                out.append(px)
    for m in AUTH_RE.finditer(text):
        proto, user, pwd, ip, port = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
        p2 = proto.upper() if proto else ptype
        if p2 == "HTTP" and proto and proto.lower() == "https":
            p2 = "HTTPS"
        px = norm_proxy(ip, port, p2, source=source, username=user or "", password=pwd or "")
        if px:
            k = (px["ip"], px["port"], px.get("username", ""))
            if k not in seen:
                seen.add(k)
                out.append(px)
    return out


def format_proxy(px, fmt="ip:port"):
    # tipos URI con clave (SS/TROJAN/VLESS...) -> exporta URI completa
    if px.get("uri") and fmt in ("ip:port", "protocol://ip:port"):
        return px["uri"]
    ip, port = px.get("ip", ""), px.get("port", "")
    user, pwd = px.get("username", "") or "", px.get("password", "") or ""
    proto = px.get("type", "HTTP").lower()
    if proto == "https":
        proto = "http"  # para URL usamos http:// (el chequeo SSL va aparte)
    has_auth = bool(user)
    if fmt == "ip:port":
        return f"{ip}:{port}"
    if fmt == "protocol://ip:port":
        return f"{proto}://{ip}:{port}"
    if fmt == "user:pass@ip:port":
        return f"{user}:{pwd}@{ip}:{port}" if has_auth else f"{ip}:{port}"
    if fmt == "protocol://user:pass@ip:port":
        return f"{proto}://{user}:{pwd}@{ip}:{port}" if has_auth else f"{proto}://{ip}:{port}"
    if fmt == "ip:port:user:pass":
        return f"{ip}:{port}:{user}:{pwd}" if has_auth else f"{ip}:{port}"
    return f"{ip}:{port}"


def scrape_txt_url(url, ptype, source, timeout=25):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
        # algunos raw vienen como ip:port por linea, otros como tabla
        found = scrape_text_blob(r.text[:500000], ptype, source)
        return found
    except Exception as e:
        print(f"[!] TXT {source}: {e}")
        return []


def scrape_uri_list(url, ptype, source, timeout=30, max_lines=5000):
    """Listas con auth real: ss://, trojan://, vless://, vmess://... (llevan contraseña/clave)."""
    import urllib.parse as _up
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
        out = []
        for line in r.text.splitlines()[:max_lines]:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            low = line.lower()
            if not (low.startswith("ss://") or low.startswith("trojan://") or low.startswith("vless://")
                    or low.startswith("vmess://") or low.startswith("ssr://") or low.startswith("tuic://")
                    or low.startswith("anytls://") or low.startswith("hy2://") or low.startswith("hysteria")):
                continue
            try:
                # intenta sacar host/puerto para validar y mostrar
                body = line.split("://", 1)[1]
                body = body.split("#")[0].split("?")[0]
                cred, _, hostport = body.rpartition("@")
                hostport = hostport.split("/")[0]
                host, _, port = hostport.rpartition(":")
                host = _up.unquote(host or "").strip("[] ")
                port = int("".join(c for c in port if c.isdigit()) or 0)
                if not host or not 1 <= port <= 65535:
                    # guarda igual aunque no parsee host (para exportar URI completa)
                    out.append({"ip": line[:60], "port": 0, "type": ptype, "country": "--",
                                "anonymity": "unknown", "source": source, "latency": -1,
                                "username": "", "password": "", "uri": line})
                    continue
                out.append({"ip": host, "port": port, "type": ptype, "country": "--",
                            "anonymity": "unknown", "source": source, "latency": -1,
                            "username": cred[:80] if cred else "", "password": "uri-key",
                            "uri": line})
            except Exception:
                continue
        return out
    except Exception as e:
        print(f"[!] URI {source}: {e}")
        return []


def scrape_table_html(html, default_type, source):
    out = []
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        return scrape_text_blob(html, default_type, source)
    tables = soup.find_all("table")
    if not tables:
        return scrape_text_blob(soup.get_text(), default_type, source)
    for table in tables:
        for tr in table.find_all("tr")[1:]:
            tds = [td.get_text(strip=True) for td in tr.find_all("td")]
            if len(tds) < 2:
                continue
            # busca primera celda que parezca IP y siguiente que parezca puerto
            ip = port = None
            for i, c in enumerate(tds[:4]):
                if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", c):
                    ip = c
                    if i + 1 < len(tds) and tds[i + 1].isdigit():
                        port = tds[i + 1]
                    break
            if not ip or not port:
                continue
            # free-proxy-list: tds[2]=Code(US), tds[3]=Country largo. Preferimos codigo 2 letras.
            country = "--"
            if len(tds) > 2 and re.match(r"^[A-Z]{2}$", tds[2].strip()):
                country = tds[2].strip().upper()
            elif len(tds) > 3 and tds[3]:
                country = tds[3].strip().upper()[:2] if len(tds[3].strip()) == 2 else tds[3].strip()[:20]
            anonymity = tds[4] if len(tds) > 4 else "unknown"
            https = tds[6].lower() if len(tds) > 6 else "no"
            ptype = "HTTPS" if https == "yes" else default_type
            px = norm_proxy(ip, port, ptype, country, anonymity, source)
            if px:
                out.append(px)
    if not out:
        out = scrape_text_blob(soup.get_text(), default_type, source)
    return out


def scrape_geonode(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=25).json()
        out = []
        for d in r.get("data", []):
            protos = d.get("protocols") or ["http"]
            pt = str(protos[0])
            px = norm_proxy(d.get("ip"), d.get("port"), pt,
                            d.get("country", "--"), d.get("anonymityLevel", "unknown"), "geonode")
            if px:
                out.append(px)
        return out
    except Exception as e:
        print(f"[!] geonode: {e}")
        return []


def scrape_proxyscrape(protocol):
    try:
        base = parse_sources()["proxyscrape_base"] + protocol
        return scrape_txt_url(base, protocol.upper(), f"proxyscrape-{protocol}")
    except Exception:
        return []


def scrape_with_browser(context, log, stop_event, wanted_types):
    """Visita TODAS las tablas de sources.json + Google y scrapea links nuevos."""
    proxies = []
    src = parse_sources()
    page = context.new_page()
    tables = src.get("tables", [])
    log(f"[*] Tablas a visitar: {len(tables)}")
    for s in tables:
        if stop_event.is_set():
            break
        try:
            log(f"[+] Visitando {s['name']} {s['url']}")
            page.goto(s["url"], timeout=35000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            try:
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(1200)
            except Exception:
                pass
            found = scrape_table_html(page.content(), s["default_type"], s["name"])
            # filtra por tipo pedido solo si la tabla trae tipo mezclado
            log(f"  -> {len(found)} de {s['name']}")
            proxies += found
        except Exception as e:
            log(f"[!] {s['name']}: {e}")
    # Google: busca y SCRAPEA los links encontrados
    try:
        for q in src.get("google_queries", [])[:3]:
            if stop_event.is_set():
                break
            log(f"[+] Google: {q}")
            page.goto("https://www.google.com/search?q=" + urllib.parse.quote(q) + "&num=10",
                      timeout=35000, wait_until="domcontentloaded")
            page.wait_for_timeout(2500)
            links = []
            try:
                links = page.eval_on_selector_all("div#search a", "els => els.map(e => e.href).filter(h => h && h.startsWith('http')).slice(0,10)")
            except Exception:
                pass
            log(f"  -> {len(links)} links")
            for u in links[:5]:
                if stop_event.is_set():
                    break
                if any(d in u for d in ["google.", "youtube.", "facebook.", "support.google"]):
                    continue
                try:
                    log(f"  [g] {u[:80]}")
                    page.goto(u, timeout=25000, wait_until="domcontentloaded")
                    page.wait_for_timeout(2000)
                    txt = page.content()
                    # intenta adivinar tipo por URL
                    pt = "HTTP"
                    if "socks5" in u.lower():
                        pt = "SOCKS5"
                    elif "socks4" in u.lower():
                        pt = "SOCKS4"
                    found = scrape_text_blob(txt, pt, "google:" + urllib.parse.urlparse(u).netloc)
                    # si no hay tipo claro, duplica como HTTP y SOCKS5 para no perder
                    log(f"      -> {len(found)}")
                    proxies += found[:2000]
                except Exception as e:
                    log(f"      [!] {e}")
                    continue
            time.sleep(1)
    except Exception as e:
        log(f"[!] Google: {e}")
    try:
        page.close()
    except Exception:
        pass
    return proxies


def scrape_fast_apis(log, wanted_types):
    from concurrent.futures import ThreadPoolExecutor, as_completed
    src = parse_sources()
    jobs = []
    # 1. GitHub masivo
    for g in src.get("github_raw", []):
        if g["type"] not in wanted_types:
            if not (g["name"] in ("clarketm-raw", "sunny-proxy", "thordata-all", "hproxy-all", "hproxy-live", "vpslab-all", "pscdn-all") and "HTTP" in wanted_types):
                continue
        jobs.append(("github", g["name"], g["url"], g["type"]))
    # 2. TXT
    for t in src.get("txt_apis", []):
        if t["type"] not in wanted_types:
            # spys-me-txt trae mezcla, incluir si HTTP pedido
            if not (t["name"] == "spys-me-txt" and "HTTP" in wanted_types):
                continue
        jobs.append(("txt", t["name"], t["url"], t["type"]))
    log(f"[*] FAST jobs: {len(jobs)} fuentes (hilos paralelos)")

    out = []
    def fetch(job):
        kind, name, url, ptype = job
        try:
            if kind == "uri":
                found = scrape_uri_list(url, ptype, name)
            else:
                found = scrape_txt_url(url, ptype, name)
            return name, found, None
        except Exception as e:
            return name, [], str(e)

    with ThreadPoolExecutor(max_workers=12) as ex:
        futs = {ex.submit(fetch, j): j for j in jobs}
        for fu in as_completed(futs):
            name, found, err = fu.result()
            if err:
                log(f"[!] {name}: {err}")
            else:
                log(f"[+] {name} -> {len(found)}")
            out += found
    # 2b. URI con auth (SS/TROJAN/VLESS...) - solo si los pides
    for u in src.get("uri_lists", []):
        if u["type"] not in wanted_types:
            continue
        log(f"[+] URI {u['name']} ({u['type']} con clave)")
        found = scrape_uri_list(u["url"], u["type"], u["name"])
        log(f"  -> {len(found)}")
        out += found
    # 3. JSON (pocos, secuencial)
    for j in src.get("json_apis", []):
        log(f"[+] API JSON {j['name']}")
        found = scrape_geonode(j["url"])
        log(f"  -> {len(found)}")
        out += found
    # 4. Proxyscrape
    for proto in ["http", "socks4", "socks5"]:
        needed = proto.upper() in wanted_types or (proto == "http" and "HTTPS" in wanted_types)
        if needed:
            log(f"[+] Proxyscrape {proto}")
            found = scrape_proxyscrape(proto)
            log(f"  -> {len(found)}")
            out += found
    log(f"[*] FAST total bruto: {len(out)}")
    return out


def stop_flag(log, g):
    return False
