"""Download source datasets and record provenance (never committed to git).

* OGIM is downloaded once to local disk and verified against the MD5 reported by
  the Zenodo API. Remote ``/vsicurl/`` reads were unreliable in the v0.1 session
  ("database disk image is malformed"), so the pipeline reads a verified local copy.
* The OGIM licence is read from the Zenodo API and written to the manifest, so it
  is recorded for every run. Read it before any redistribution.
"""
from __future__ import annotations

import glob
import json
import logging
import os
import re
import time
import zipfile
from typing import Optional

from . import config as C
from .release import md5_file, sha256_file, utc_now_iso

log = logging.getLogger("nowri")
UA = {"User-Agent": "Mozilla/5.0 (NOWRI research pipeline)"}


def _requests():
    import requests  # imported lazily so that pure-logic tests do not need it
    return requests


def fetch_json(url: str, timeout: int = 60, retries: int = 3) -> dict:
    last = None
    for attempt in range(1, retries + 1):
        try:
            r = _requests().get(url, timeout=timeout, headers=UA)
            r.raise_for_status()
            return r.json()
        except Exception as exc:  # noqa: BLE001
            last = exc
            log.warning("GET %s failed (attempt %d/%d): %s", url, attempt, retries, exc)
            time.sleep(2 * attempt)
    raise RuntimeError(f"Could not fetch {url}: {last}")


class DownloadError(RuntimeError):
    """The server answered, but not with the file we expected (e.g. a web page instead of a zip)."""


BROWSER_UA = {
    "User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0 Safari/537.36"),
    "Accept": "*/*",
}


def download_file(url: str, dest: str, retries: int = 3, chunk: int = 8 << 20,
                  expect_zip: bool = False, min_bytes: int = 0, headers: Optional[dict] = None) -> str:
    """Stream a file to disk (atomic rename on success) and check that it is the file we asked for.

    ``expect_zip`` rejects responses that do not start with the zip signature (typically an HTML
    page from a bot-protection or error screen). ``min_bytes`` rejects truncated or tiny files.
    """
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    tmp = dest + ".part"
    last = None
    for attempt in range(1, retries + 1):
        try:
            with _requests().get(url, stream=True, timeout=120, headers=headers or UA,
                                 allow_redirects=True) as r:
                r.raise_for_status()
                total = int(r.headers.get("Content-Length", 0) or 0)
                blocks = r.iter_content(chunk_size=chunk)
                first = next(blocks, b"")
                if expect_zip and not first.startswith(b"PK"):
                    raise DownloadError(
                        f"{url} answered HTTP {r.status_code}, content-type {r.headers.get('Content-Type')!r}, "
                        f"{len(first)} bytes, which is not a zip file. First bytes: {first[:160]!r}")
                done, t0, mark = len(first), time.time(), 0
                with open(tmp, "wb") as f:
                    f.write(first)
                    for block in blocks:
                        f.write(block)
                        done += len(block)
                        if total and done - mark > 256 * (1 << 20):
                            mark = done
                            log.info("  downloaded %.0f / %.0f MB (%.0f s)",
                                     done / 1e6, total / 1e6, time.time() - t0)
            size = os.path.getsize(tmp)
            if min_bytes and size < min_bytes:
                raise DownloadError(f"{url} gave only {size} bytes (expected at least {min_bytes}).")
            os.replace(tmp, dest)
            return dest
        except DownloadError:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise                      # a wrong answer will not improve by retrying
        except Exception as exc:  # noqa: BLE001
            last = exc
            log.warning("download %s failed (attempt %d/%d): %s", url, attempt, retries, exc)
            time.sleep(5 * attempt)
    raise RuntimeError(f"Could not download {url}: {last}")


def _licence_from_zenodo(md: dict) -> str:
    lic = md.get("license")
    if isinstance(lic, dict):
        lic = lic.get("id") or lic.get("title")
    if not lic:
        rights = md.get("rights")
        if isinstance(rights, list) and rights:
            names = []
            for r in rights:
                t = r.get("title")
                if isinstance(t, dict):
                    t = t.get("en") or next(iter(t.values()), None)
                names.append(str(t or r.get("id") or r))
            lic = "; ".join(names)
    return str(lic) if lic else "NOT FOUND IN API RESPONSE - read the Zenodo record page"


def fetch_ogim(workdir: str, ogim_path: Optional[str] = None) -> dict:
    """Return provenance dict for OGIM, downloading and verifying if needed."""
    info = {
        "name": "Oil and Gas Infrastructure Mapping (OGIM) database",
        "version": C.OGIM_VERSION, "doi": C.OGIM_DOI,
        "url": f"https://zenodo.org/records/{C.OGIM_RECORD_ID}",
        "citation": C.OGIM_CITATION,
        "access_date_utc": utc_now_iso(),
    }
    expected_md5 = C.OGIM_MD5_OBSERVED
    download_url = C.OGIM_FILE_URL
    try:
        rec = fetch_json(C.OGIM_API_URL)
        md = rec.get("metadata", {})
        info["title"] = md.get("title")
        info["publication_date"] = md.get("publication_date")
        info["licence_recorded"] = _licence_from_zenodo(md)
        info["zenodo_metadata_license_raw"] = md.get("license")
        info["zenodo_metadata_rights_raw"] = md.get("rights")
        for item in rec.get("files", []):
            if item.get("key") == C.OGIM_FILENAME:
                cs = str(item.get("checksum", ""))
                if cs.startswith("md5:"):
                    expected_md5 = cs.split(":", 1)[1]
                info["expected_size_bytes"] = item.get("size")
                link = (item.get("links") or {}).get("self")
                if link:
                    download_url = link
    except Exception as exc:  # noqa: BLE001
        log.warning("Zenodo API unavailable (%s); using hard-coded checksum.", exc)
        info["licence_recorded"] = "NOT RETRIEVED (API unavailable) - read the Zenodo record page"
    log.info("OGIM licence recorded from Zenodo API: %s", info["licence_recorded"])

    path = ogim_path or os.path.join(workdir, C.OGIM_FILENAME)
    if os.path.exists(path):
        log.info("Verifying existing OGIM file %s ...", path)
        if md5_file(path) != expected_md5:
            if ogim_path:
                raise RuntimeError(f"{path} does not match expected MD5 {expected_md5}")
            log.warning("Existing file has the wrong checksum; re-downloading.")
            os.remove(path)
    if not os.path.exists(path):
        log.info("Downloading OGIM v3.0 (~3.4 GB) - this can take several minutes ...")
        download_file(download_url, path)
        got = md5_file(path)
        if got != expected_md5:
            raise RuntimeError(f"OGIM checksum mismatch: expected {expected_md5}, got {got}")
    info.update({"path": path, "md5_verified": expected_md5,
                 "size_bytes": os.path.getsize(path)})
    return info


def fetch_hydrorivers(workdir: str) -> dict:
    info = {
        "name": "HydroRIVERS", "version": "v1.0", "region": "Africa",
        "url": C.HYDRORIVERS_URL, "citation": C.HYDRORIVERS_CITATION,
        "source_resolution": "15 arc-seconds",
        "access_date_utc": utc_now_iso(),
        "licence_recorded": ("HydroSHEDS version 1 licence agreement (Technical Documentation v1.4, Appendix A): "
                             "free for non-commercial and commercial use; stand-alone redistribution of the "
                             "licensed data is prohibited; derived products distributed to end users need an "
                             "end-user licence at least as protective and the mandatory Exhibit B attribution. "
                             "Whether published derived attributes (distances/flags) are permitted has not been "
                             "confirmed with the provider."),
    }
    zpath = os.path.join(workdir, "HydroRIVERS_Africa.zip")
    folder = os.path.join(workdir, "hydrorivers")
    shps = glob.glob(os.path.join(folder, "**", C.HYDRORIVERS_SHP), recursive=True)
    if not shps:
        if not os.path.exists(zpath):
            log.info("Downloading HydroRIVERS Africa (~100 MB) ...")
            download_file(C.HYDRORIVERS_URL, zpath)
        with zipfile.ZipFile(zpath) as z:
            z.extractall(folder)
        shps = glob.glob(os.path.join(folder, "**", C.HYDRORIVERS_SHP), recursive=True)
    if not shps:
        raise FileNotFoundError(f"{C.HYDRORIVERS_SHP} not found after extraction in {folder}")
    info["path"] = shps[0]
    if os.path.exists(zpath):
        info["zip_sha256"] = sha256_file(zpath)
    return info


def select_zip_members(names, pattern: str):
    """Names in a zip that match a (case-insensitive) pattern, sorted."""
    rx = re.compile(pattern, re.I)
    return sorted(n for n in names if rx.search(n))


def extract_tiles(zip_path: str, dest: str, pattern: str, _depth: int = 0) -> list:
    """Extract only the members matching ``pattern`` (and return the .shp paths).

    Works on the zip's directory, so the 2.5 GB archive is never fully unpacked.
    If no shapefile matches but the zip contains inner zips, those are searched too (one level).
    """
    os.makedirs(dest, exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        members = select_zip_members(names, pattern)
        shp = [m for m in members if m.lower().endswith(".shp")]
        if shp:
            for m in members:
                z.extract(m, dest)
            return sorted(os.path.join(dest, m) for m in shp)
        inner = [n for n in names if n.lower().endswith(".zip")]
        if inner and _depth == 0:
            found = []
            for n in inner:
                z.extract(n, dest)
                try:
                    found += extract_tiles(os.path.join(dest, n), dest, pattern, _depth=1)
                except FileNotFoundError:
                    continue
            if found:
                return sorted(found)
        sample = [n for n in names if n.lower().endswith((".shp", ".zip"))][:40]
        raise FileNotFoundError(
            f"No Africa RiverATLAS shapefile matched {pattern!r} in {zip_path}. "
            f"Shapefile/zip names found (first 40): {sample}")


def fetch_riveratlas(workdir: str, zip_path: Optional[str] = None) -> dict:
    """RiverATLAS v1.0 (HydroATLAS), Africa tiles. Provider licence: CC BY 4.0 (Collective Database).

    ``zip_path`` lets you supply the 2.55 GB shapefile zip yourself (for example from Google Drive)
    if the automatic download is blocked.
    """
    info = {
        "name": "HydroATLAS - RiverATLAS (river reach lines)", "version": "v1.0 (Africa tiles)",
        "url": "https://www.hydrosheds.org/products/hydroatlas", "download_url": C.RIVERATLAS_URL,
        "citation": C.RIVERATLAS_CITATION, "source_resolution": "15 arc-seconds",
        "access_date_utc": utc_now_iso(),
        "licence_recorded": ("CC BY 4.0: HydroATLAS is licensed as a Collective Database under CC BY 4.0 per the "
                             "provider's product page and HydroATLAS Technical Documentation v1.0.1 section 4.1. "
                             "Individual parts keep their own licences and the original HydroSHEDS/HydroRIVERS "
                             "licences are unaffected. Contains the same reaches and HYRIV_ID as HydroRIVERS."),
    }
    folder = os.path.join(workdir, "riveratlas")
    existing = []
    if os.path.isdir(folder):
        existing = sorted(glob.glob(os.path.join(folder, "**", "RiverATLAS_v10_af*.shp"), recursive=True))
    zpath = zip_path or os.path.join(workdir, C.RIVERATLAS_ZIP)
    if not existing:
        usable = (os.path.exists(zpath) and os.path.getsize(zpath) >= C.RIVERATLAS_MIN_BYTES
                  and zipfile.is_zipfile(zpath))
        if zip_path and not usable:
            raise FileNotFoundError(f"--riveratlas-zip {zip_path!r} is missing, too small or not a zip file.")
        if not usable:
            if os.path.exists(zpath):
                log.warning("Removing unusable earlier download %s (%d bytes).", zpath, os.path.getsize(zpath))
                os.remove(zpath)
            errors = []
            for url in (C.RIVERATLAS_URL, C.RIVERATLAS_API_URL):
                log.info("Downloading RiverATLAS shapefiles (~2.55 GB, one-off) from %s ...", url)
                try:
                    download_file(url, zpath, expect_zip=True, min_bytes=C.RIVERATLAS_MIN_BYTES,
                                  headers=BROWSER_UA)
                    break
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"- {url}\n    {exc}")
                    log.warning("Route failed: %s", exc)
            else:
                raise RuntimeError(
                    "Could not download RiverATLAS automatically. What each route returned:\n"
                    + "\n".join(errors)
                    + "\n\nManual route: download 'Global RiverATLAS in shapefile format (2.55GB)' from "
                      "https://www.hydrosheds.org/products/hydroatlas in your browser, put the zip in Google "
                      "Drive, mount Drive in Colab, and run the pipeline with "
                      "--riveratlas-zip /content/drive/MyDrive/<file name>.zip")
        existing = extract_tiles(zpath, folder, C.RIVERATLAS_TILE_PATTERN)
    log.info("RiverATLAS Africa tiles: %s", [os.path.basename(p) for p in existing])
    info["paths"] = existing
    info["tiles"] = [os.path.basename(p) for p in existing]
    if os.path.exists(zpath) and zipfile.is_zipfile(zpath):
        info["zip_sha256"] = sha256_file(zpath)
    return info


def fetch_boundaries(workdir: str) -> dict:
    meta = fetch_json(C.GEOBOUNDARIES_API)
    path = os.path.join(workdir, "nigeria_adm1_geoboundaries.geojson")
    if not os.path.exists(path):
        download_file(meta["gjDownloadURL"], path)
    return {
        "name": "geoBoundaries ADM1 (Nigeria)", "version": "gbOpen/current",
        "boundary_name": meta.get("boundaryName"), "boundary_type": meta.get("boundaryType"),
        "year_represented": meta.get("boundaryYearRepresented"),
        "boundary_source": meta.get("boundarySource"),
        "url": C.GEOBOUNDARIES_API, "download_url": meta.get("gjDownloadURL"),
        "licence_recorded": meta.get("boundaryLicense"),
        "access_date_utc": utc_now_iso(), "path": path,
    }


def public_source_record(info: dict) -> dict:
    """Source record safe for the manifest (drops local filesystem paths)."""
    return {k: v for k, v in info.items() if k not in ("path", "paths")}
