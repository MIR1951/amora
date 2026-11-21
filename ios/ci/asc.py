#!/usr/bin/env python3
"""App Store Connect API yordamchisi: TestFlight'ga yuklash uchun imzo tayyorlaydi va tozalaydi.

    python3 ios/ci/asc.py check   --bundle-id uz.amora.app --min-build 12
    python3 ios/ci/asc.py signing --bundle-id uz.amora.app --out "$RUNNER_TEMP/signing"
    python3 ios/ci/asc.py cleanup --out "$RUNNER_TEMP/signing"

Kalitlar muhit o'zgaruvchilaridan olinadi (GitHub Actions sirlari):
    ASC_KEY_ID, ASC_ISSUER_ID   - App Store Connect API kaliti
    ASC_KEY_PATH                - .p8 fayl yo'li (workflow sirdan yozib qo'yadi)

Nega shunday: Mac yo'q va sertifikatni saqlab qo'yadigan joy yo'q. Shuning uchun har yuklashda
yangi "Apple Distribution" sertifikati (kaliti faqat shu runner'da yaratiladi) va unga App Store
profili yaratiladi, ilova imzolanib yuklangach ikkalasi ham o'chiriladi (`cleanup`). TestFlight va
App Store'dagi ilovani Apple o'zi qayta imzolaydi, shuning uchun sertifikatni o'chirish yuklangan
build'ga ta'sir qilmaydi. Akkauntdagi boshqa sertifikat va profillarga tegilmaydi: faqat nomi
"Amora CI" bilan boshlanadigan profillar va ularning sertifikatlari.

Faqat standart kutubxona + PyJWT[crypto] (pip install "pyjwt[crypto]").
"""

import argparse
import base64
import json
import os
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import jwt
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID

API = "https://api.appstoreconnect.apple.com/v1"
PROFILE_PREFIX = "Amora CI"
CERT_TYPE = "DISTRIBUTION"  # "Apple Distribution" (Xcode 11+)


class AscError(Exception):
    pass


def fail(message: str) -> None:
    print(f"::error::{message}")
    sys.exit(1)


class Client:
    def __init__(self, key_id: str, issuer_id: str, key_path: Path):
        self.key_id = key_id
        self.issuer_id = issuer_id
        try:
            raw = key_path.read_text(encoding="utf-8")
        except OSError as error:
            raise AscError(f"API kaliti fayli o'qilmadi: {error}") from error
        self.private_key = normalize_p8(raw)
        # altool ham shu fayldan o'qiydi: tuzatilgan ko'rinishini qayta yozamiz
        key_path.write_text(self.private_key, encoding="utf-8")
        self._token = ""
        self._token_expires = 0.0

    def token(self) -> str:
        now = int(time.time())
        if self._token and now < self._token_expires - 60:
            return self._token
        try:
            self._token = jwt.encode(
                {"iss": self.issuer_id, "iat": now, "exp": now + 15 * 60, "aud": "appstoreconnect-v1"},
                self.private_key,
                algorithm="ES256",
                headers={"kid": self.key_id, "typ": "JWT"},
            )
        except (jwt.PyJWTError, ValueError, TypeError) as error:
            raise AscError(f"API kaliti yaroqsiz (.p8 buzilgan bo'lishi mumkin): {error}") from error
        self._token_expires = now + 15 * 60
        return self._token

    def request(self, method: str, path: str, body: dict | None = None, query: dict | None = None) -> dict:
        url = path if path.startswith("https://") else f"{API}{path}"
        if query:
            url += "?" + urllib.parse.urlencode(query)
        data = json.dumps(body).encode() if body is not None else None
        for attempt in range(4):
            req = urllib.request.Request(url, data=data, method=method)
            req.add_header("Authorization", f"Bearer {self.token()}")
            if data is not None:
                req.add_header("Content-Type", "application/json")
            try:
                with urllib.request.urlopen(req, timeout=60) as response:
                    text = response.read().decode() or "{}"
                    return json.loads(text) if text.strip() else {}
            except urllib.error.HTTPError as error:
                text = error.read().decode(errors="replace")
                if error.code in (429, 500, 502, 503, 504) and attempt < 3:
                    time.sleep(3 * (attempt + 1))
                    continue
                raise AscError(_explain(error.code, method, path, text)) from None
            except urllib.error.URLError as error:
                if attempt < 3:
                    time.sleep(3 * (attempt + 1))
                    continue
                raise AscError(f"Apple serveriga ulanib bo'lmadi: {error}") from None
        raise AscError("Apple serveri javob bermadi")

    def get_all(self, path: str, query: dict | None = None) -> list[dict]:
        result: list[dict] = []
        page = self.request("GET", path, query={"limit": 200, **(query or {})})
        while True:
            result.extend(page.get("data", []))
            next_url = page.get("links", {}).get("next")
            if not next_url:
                return result
            page = self.request("GET", next_url)


def normalize_p8(raw: str) -> str:
    """Sirga .p8 turli ko'rinishda qo'yilishi mumkin: to'liq fayl, BEGIN/END qatorlarisiz faqat
    o'rtasi, butun faylning base64 ko'rinishi yoki "\\n" bilan bitta qator. Hammasini PEM ga keltiradi.
    Kalit matni jurnalga hech qachon chiqmaydi."""
    text = raw.strip().strip('"').strip("'").replace("\\n", "\n").replace("\r", "")
    if "BEGIN PRIVATE KEY" in text:
        return text + "\n"
    compact = "".join(text.split())
    try:
        decoded = base64.b64decode(compact, validate=True)
    except ValueError:
        decoded = b""
    if b"BEGIN PRIVATE KEY" in decoded:
        return decoded.decode("utf-8", "replace").strip() + "\n"
    if decoded:
        try:
            serialization.load_der_private_key(decoded, password=None)
            body = "\n".join(compact[i : i + 64] for i in range(0, len(compact), 64))
            return f"-----BEGIN PRIVATE KEY-----\n{body}\n-----END PRIVATE KEY-----\n"
        except (ValueError, TypeError):
            pass
    raise AscError(
        "ASC_KEY_P8 siri .p8 kalit emas (uzunligi "
        f"{len(text)} belgi, to'g'ri kalit ~250 belgi bo'ladi). App Store Connect API sahifasidan "
        "yuklangan AuthKey_XXXX.p8 faylni Notepad'da oching va BEGIN/END qatorlari bilan birga "
        "hammasini nusxa qilib, sirni qayta saqlang. Key ID, Issuer ID yoki push kaliti (Amora Push) "
        "emas, aynan API kaliti fayli kerak"
    )


def _explain(status: int, method: str, path: str, text: str) -> str:
    detail = text[:600]
    try:
        errors = json.loads(text).get("errors", [])
        if errors:
            detail = "; ".join(f"{e.get('title', '')}: {e.get('detail', '')}" for e in errors)
    except ValueError:
        pass
    if status == 401:
        return (
            "Apple API kalitni qabul qilmadi (401). ASC_KEY_ID, ASC_ISSUER_ID va ASC_KEY_P8 sirlari "
            f"bir xil kalitga tegishlimi, kalit bekor qilinmaganmi tekshiring. {detail}"
        )
    if status == 403:
        return (
            "Kalitga ruxsat yetmaydi (403). App Store Connect API kaliti Admin roli bilan "
            f"yaratilgan bo'lishi kerak. {detail}"
        )
    return f"Apple API xatosi {status} ({method} {path.split('?')[0]}): {detail}"


def client_from_env() -> Client:
    missing = [name for name in ("ASC_KEY_ID", "ASC_ISSUER_ID", "ASC_KEY_PATH") if not os.environ.get(name)]
    if missing:
        raise AscError("Sirlar yetishmaydi: " + ", ".join(missing))
    return Client(os.environ["ASC_KEY_ID"].strip(), os.environ["ASC_ISSUER_ID"].strip(), Path(os.environ["ASC_KEY_PATH"]))


def output(name: str, value: str) -> None:
    print(f"{name}={value}")
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(f"{name}={value}\n")


# ---------------------------------------------------------------- check


def find_bundle_id(client: Client, identifier: str) -> dict | None:
    items = client.get_all("/bundleIds", {"filter[identifier]": identifier, "filter[platform]": "IOS"})
    # filter[identifier] qisman moslikni ham qaytaradi (uz.amora.app.uitests): aniq tengini olamiz
    return next((item for item in items if item["attributes"]["identifier"] == identifier), None)


def ensure_bundle_id(client: Client, identifier: str) -> dict:
    bundle = find_bundle_id(client, identifier)
    if bundle is None:
        print(f"Bundle ID {identifier} topilmadi: yaratilmoqda")
        bundle = client.request(
            "POST",
            "/bundleIds",
            {"data": {"type": "bundleIds", "attributes": {"identifier": identifier, "name": "Amora", "platform": "IOS"}}},
        )["data"]
    # Bu bog'lanish "limit" parametrini qabul qilmaydi: oddiy so'rov
    capabilities = client.request("GET", f"/bundleIds/{bundle['id']}/bundleIdCapabilities").get("data", [])
    kinds = {item["attributes"]["capabilityType"] for item in capabilities}
    if "PUSH_NOTIFICATIONS" not in kinds:
        print("Push Notifications imkoniyati yoqilmoqda")
        client.request(
            "POST",
            "/bundleIdCapabilities",
            {
                "data": {
                    "type": "bundleIdCapabilities",
                    "attributes": {"capabilityType": "PUSH_NOTIFICATIONS"},
                    "relationships": {"bundleId": {"data": {"type": "bundleIds", "id": bundle["id"]}}},
                }
            },
        )
    return bundle


def cmd_check(args: argparse.Namespace) -> None:
    client = client_from_env()
    bundle = ensure_bundle_id(client, args.bundle_id)
    print(f"Bundle ID: {args.bundle_id} ({bundle['id']}), Push Notifications yoqilgan")
    apps = client.get_all("/apps", {"filter[bundleId]": args.bundle_id})
    app = next((item for item in apps if item["attributes"]["bundleId"] == args.bundle_id), None)
    if app is None:
        raise AscError(
            f"App Store Connect'da {args.bundle_id} uchun ilova yozuvi yo'q. appstoreconnect.apple.com → "
            "Apps → + → New App (Bundle ID: uz.amora.app) qilib yarating va qayta ishga tushiring"
        )
    print(f"Ilova: {app['attributes']['name']} ({app['id']})")
    # Yangi build raqami avvalgi barcha yuklangan build'lardan katta bo'lishi shart
    latest = 0
    builds = client.request("GET", "/builds", query={"filter[app]": app["id"], "sort": "-uploadedDate", "limit": 50})
    for build in builds.get("data", []):
        try:
            latest = max(latest, int(str(build["attributes"]["version"]).split(".")[0]))
        except (ValueError, KeyError):
            continue
    build_number = max(args.min_build, latest + 1)
    print(f"Oxirgi yuklangan build: {latest or 'yo`q'}, yangisi: {build_number}")
    output("app_id", app["id"])
    output("build_number", str(build_number))


# ---------------------------------------------------------------- signing


def make_csr(common_name: str) -> tuple[rsa.RSAPrivateKey, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    csr = (
        x509.CertificateSigningRequestBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)]))
        .sign(key, hashes.SHA256())
    )
    return key, csr.public_bytes(serialization.Encoding.PEM).decode()


def cleanup_leftovers(client: Client) -> None:
    """Oldingi bekor qilingan ishlardan qolgan "Amora CI" profillari va ularning sertifikatlari."""
    profiles = client.get_all("/profiles", {"filter[profileType]": "IOS_APP_STORE", "include": "certificates"})
    for profile in profiles:
        if not profile["attributes"]["name"].startswith(PROFILE_PREFIX):
            continue
        certs = profile.get("relationships", {}).get("certificates", {}).get("data", []) or []
        _revoke_and_delete(client, profile["id"], [cert["id"] for cert in certs])


def _revoke_and_delete(client: Client, profile_id: str | None, cert_ids: list[str]) -> None:
    for cert_id in cert_ids:
        try:
            client.request("DELETE", f"/certificates/{cert_id}")
            print(f"Sertifikat {cert_id} o'chirildi")
        except AscError as error:
            print(f"[ogohlantirish] sertifikat {cert_id}: {error}")
    if profile_id:
        try:
            client.request("DELETE", f"/profiles/{profile_id}")
            print(f"Profil {profile_id} o'chirildi")
        except AscError as error:
            print(f"[ogohlantirish] profil {profile_id}: {error}")


def cmd_signing(args: argparse.Namespace) -> None:
    client = client_from_env()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    state_path = out / "state.json"
    state: dict = {"certificate_id": None, "profile_id": None}

    cleanup_leftovers(client)
    bundle = find_bundle_id(client, args.bundle_id)
    if bundle is None:
        raise AscError(f"Bundle ID {args.bundle_id} topilmadi (avval `check` ishlashi kerak)")

    key, csr = make_csr("Amora CI")
    try:
        cert = client.request(
            "POST",
            "/certificates",
            {"data": {"type": "certificates", "attributes": {"certificateType": CERT_TYPE, "csrContent": csr}}},
        )["data"]
    except AscError as error:
        if "maximum" in str(error).lower() or "limit" in str(error).lower():
            raise AscError(
                "Akkauntda Apple Distribution sertifikatlari soni chegarada (3 ta). developer.apple.com → "
                "Certificates bo'limida keraksizini o'chirish kerak (akkaunt egasi bilan kelishib). "
                f"{error}"
            ) from None
        raise
    state["certificate_id"] = cert["id"]
    state_path.write_text(json.dumps(state))
    print(f"Vaqtinchalik sertifikat yaratildi: {cert['id']}")

    certificate = x509.load_der_x509_certificate(base64.b64decode(cert["attributes"]["certificateContent"]))
    password = secrets.token_urlsafe(24)
    # macOS `security import` yangi AES shifrli p12 ni o'qimaydi: eski 3DES/SHA1 shifri
    encryption = (
        serialization.PrivateFormat.PKCS12.encryption_builder()
        .kdf_rounds(50000)
        .key_cert_algorithm(pkcs12.PBES.PBESv1SHA1And3KeyTripleDESCBC)
        .hmac_hash(hashes.SHA1())
        .build(password.encode())
    )
    (out / "dist.p12").write_bytes(
        pkcs12.serialize_key_and_certificates(b"Amora CI", key, certificate, None, encryption)
    )

    profile_name = f"{PROFILE_PREFIX} {os.environ.get('GITHUB_RUN_ID', int(time.time()))}"
    profile = client.request(
        "POST",
        "/profiles",
        {
            "data": {
                "type": "profiles",
                "attributes": {"name": profile_name, "profileType": "IOS_APP_STORE"},
                "relationships": {
                    "bundleId": {"data": {"type": "bundleIds", "id": bundle["id"]}},
                    "certificates": {"data": [{"type": "certificates", "id": cert["id"]}]},
                },
            }
        },
    )["data"]
    state["profile_id"] = profile["id"]
    state_path.write_text(json.dumps(state))
    (out / "profile.mobileprovision").write_bytes(base64.b64decode(profile["attributes"]["profileContent"]))
    print(f"Vaqtinchalik profil yaratildi: {profile_name} ({profile['id']})")

    # Parol faqat jurnalda yashirin ko'rinadi
    print(f"::add-mask::{password}")
    output("p12_password", password)
    output("profile_name", profile_name)
    output("profile_uuid", profile["attributes"]["uuid"])


def cmd_cleanup(args: argparse.Namespace) -> None:
    state_path = Path(args.out) / "state.json"
    if not state_path.exists():
        print("Tozalanadigan narsa yo'q")
        return
    state = json.loads(state_path.read_text())
    client = client_from_env()
    certs = [state["certificate_id"]] if state.get("certificate_id") else []
    _revoke_and_delete(client, state.get("profile_id"), certs)
    state_path.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check")
    check.add_argument("--bundle-id", required=True)
    check.add_argument("--min-build", type=int, default=1)
    signing = sub.add_parser("signing")
    signing.add_argument("--bundle-id", required=True)
    signing.add_argument("--out", required=True)
    cleanup = sub.add_parser("cleanup")
    cleanup.add_argument("--out", required=True)
    args = parser.parse_args()
    try:
        {"check": cmd_check, "signing": cmd_signing, "cleanup": cmd_cleanup}[args.command](args)
    except AscError as error:
        fail(str(error))


if __name__ == "__main__":
    main()
