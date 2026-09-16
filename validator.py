"""Validacion V2: modo rapido TCP + completo HTTP. No devuelve vacio."""
import asyncio
import time

import aiohttp

TEST_URLS = ["http://httpbin.org/ip", "http://example.com", "http://neverssl.com"]


async def tcp_ping(ip, port, timeout=4):
    t0 = time.perf_counter()
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(ip, int(port)), timeout)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return int((time.perf_counter() - t0) * 1000)
    except Exception:
        return None


def proxy_url(px):
    """Construye http://[user:pass@]ip:port para aiohttp."""
    user, pwd = px.get("username", "") or "", px.get("password", "") or ""
    if user:
        from urllib.parse import quote
        return f"http://{quote(user)}:{quote(pwd)}@{px['ip']}:{px['port']}"
    return f"http://{px['ip']}:{px['port']}"


async def http_check(session, proxy, timeout=8):
    if proxy["type"] not in ("HTTP", "HTTPS"):
        return True
    url = proxy_url(proxy)
    for tu in TEST_URLS[:2]:
        try:
            async with session.get(tu, proxy=url, timeout=aiohttp.ClientTimeout(total=timeout)) as r:
                if r.status in (200, 301, 302):
                    return True
        except Exception:
            continue
    return False


URI_TYPES = {"SS", "TROJAN", "VLESS", "VMESS", "SSR", "TUIC", "ANYTLS", "HY2"}

async def validate_one(session, sem, proxy, timeout, fast):
    async with sem:
        # URIs con clave (v2ray): si no pudimos sacar puerto, se conservan sin test
        if proxy.get("type") in URI_TYPES:
            if not proxy.get("port"):
                proxy["latency"] = -1
                return proxy
            try:
                lat = await tcp_ping(proxy["ip"], proxy["port"], timeout=4)
            except Exception:
                lat = None
            proxy["latency"] = lat if lat is not None else -1
            return proxy if lat is not None else None
        lat = await tcp_ping(proxy["ip"], proxy["port"], timeout=4)
        if lat is None:
            return None
        proxy["latency"] = lat
        if not fast and proxy["type"] in ("HTTP", "HTTPS"):
            ok = await http_check(session, proxy, timeout)
            if not ok:
                return None
        return proxy


async def _run(proxies, log, limit=100, timeout=8, fast=True):
    seen, uniq = set(), []
    for p in proxies:
        # incluye auth en dedup para no perder user:pass distintos mismo ip:port
        p.setdefault("username", "")
        p.setdefault("password", "")
        k = (p["ip"], p["port"], p.get("username", ""))
        if k not in seen:
            seen.add(k)
            uniq.append(p)
    # si pides pocos, no hace falta mirar 2500: paramos en cuanto los tengamos
    max_test = min(len(uniq), max(300, limit * 10) if fast else 2500)
    subset = uniq[:max_test]
    log(f"[*] Unicos: {len(uniq)}, voy a testear por tandas hasta conseguir {limit} (max {max_test}) modo={'RAPIDO' if fast else 'COMPLETO'}...")
    sem = asyncio.Semaphore(60)
    out = []
    tested = 0
    BATCH = 60
    async with aiohttp.ClientSession() as s:
        for i in range(0, len(subset), BATCH):
            if len(out) >= limit:
                break
            chunk = subset[i:i + BATCH]
            tasks = [asyncio.create_task(validate_one(s, sem, p, timeout, fast)) for p in chunk]
            try:
                for coro in asyncio.as_completed(tasks):
                    if len(out) >= limit:
                        break
                    r = await coro
                    tested += 1
                    if r:
                        out.append(r)
                        if len(out) >= limit:
                            break
                    if len(out) >= limit:
                        break
            finally:
                for t in tasks:
                    if not t.done():
                        t.cancel()
            log(f"  ... testeados {tested}, vivos {len(out)}/{limit}")
            if len(out) >= limit:
                log(f"[*] Objetivo conseguido ({len(out)}/{limit}). Paro, no sigo testeando.")
                break
    out.sort(key=lambda x: x["latency"])
    return out[:limit], len(uniq), tested


def validate_proxies(proxies, log=print, limit=100, timeout=8, fast=True):
    if not proxies:
        return []
    vivos, total, tested = asyncio.run(_run(proxies, log, limit, timeout, fast))
    log(f"[*] Testeados {tested}/{total}, vivos {len(vivos)}")
    return vivos
