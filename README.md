# 🌐 Proxy Scraper Pro

Aplicación de escritorio en Python que **recopila proxies públicos** de más de 100 fuentes, **comprueba cuáles funcionan** y permite filtrarlos y exportarlos.

Proyecto personal para practicar programación asíncrona, *scraping* y protocolos de red (HTTP, HTTPS, SOCKS4 y SOCKS5).

## Funciones

- **Recopilación** desde tablas HTML, listas de texto, APIs JSON y repositorios públicos, con fuentes configurables en `sources.json`.
- **Navegador automatizado** (Playwright) para las fuentes que cargan contenido con JavaScript.
- **Validación concurrente** con `asyncio` y `aiohttp`: prueba de conexión TCP y petición HTTP real a través de cada proxy, con modo rápido.
- **Filtros** por tipo, país y nivel de anonimato.
- **Entrada manual** o importación desde `.txt`, y nueva prueba de los proxies guardados.
- **Exportación** a `.txt`, `.csv` o `.json` en varios formatos (`ip:port`, URL…).

## Tecnologías

Python 3.13 · CustomTkinter · Playwright · asyncio · aiohttp / aiohttp-socks · BeautifulSoup · lxml · requests

## Estructura

| Archivo | Función |
| --- | --- |
| `main.py` | Punto de entrada. |
| `gui.py` | Interfaz gráfica con CustomTkinter. |
| `scrapers.py` | Lectura y normalización de cada tipo de fuente. |
| `browser.py` | Navegador automatizado para fuentes con JavaScript. |
| `validator.py` | Validación asíncrona de proxies. |
| `sources.json` | Lista de fuentes y países. |

## Instalación en Windows

```
instalar.bat   # instala dependencias y el navegador de Playwright
ejecutar.bat   # abre la aplicación
```

O a mano:

```
pip install -r requirements.txt
python -m playwright install chrome
python main.py
```

## Uso responsable

Los proxies públicos son de terceros y no son seguros: no envíes por ellos contraseñas ni datos personales. Usa la herramienta solo con fines de aprendizaje y respeta las condiciones de cada fuente.

---

Autor: [Pau Alarcón](https://paualarcon.com) · [LinkedIn](https://www.linkedin.com/in/pau-alarcon-ruiz-4a1424437/)
