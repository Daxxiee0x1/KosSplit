"""Payment helpers: detect the bank or e-wallet, build reminders, and WhatsApp links.

KosSplit does not log in to bank accounts. It prepares the transfer details,
copies the account number, and opens the official bank or e-wallet app so the
user confirms the transfer there.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import quote

from .money import rupiah


@dataclass(frozen=True)
class Provider:
    key: str
    label: str
    package: str
    kind: str
    aliases: tuple[str, ...]


# Ordered so that more specific names are matched first, for example blu before BCA.
PROVIDERS: tuple[Provider, ...] = (
    Provider("blu", "blu by BCA Digital", "com.bcadigital.blu", "bank", ("blu",)),
    Provider("bca", "BCA mobile", "com.bca", "bank", ("bca", "klikbca")),
    Provider("mandiri", "Livin' by Mandiri", "id.bmri.livin", "bank", ("mandiri", "livin")),
    Provider("bri", "BRImo", "id.co.bri.brimo", "bank", ("bri", "brimo")),
    Provider("bni", "BNI Mobile", "src.com.bni", "bank", ("bni", "wondr")),
    Provider("gopay", "GoPay", "com.gojek.gopay", "ewallet", ("gopay", "gojek")),
    Provider("ovo", "OVO", "ovo.id", "ewallet", ("ovo",)),
    Provider("dana", "DANA", "id.dana", "ewallet", ("dana",)),
    Provider("shopeepay", "ShopeePay", "com.shopee.id", "ewallet", ("shopeepay", "shopee")),
)

PROVIDER_NAMES = tuple(provider.label for provider in PROVIDERS)


@dataclass(frozen=True)
class PaymentTarget:
    provider: Provider | None
    account_number: str
    raw: str

    @property
    def label(self) -> str:
        return self.provider.label if self.provider else "Rekening"


def find_provider(label: str) -> Provider | None:
    return next((provider for provider in PROVIDERS if provider.label == label), None)


def parse_payment_info(text: str) -> PaymentTarget:
    lowered = text.lower()
    provider = next(
        (
            item
            for item in PROVIDERS
            if any(re.search(rf"\b{re.escape(alias)}\b", lowered) for alias in item.aliases)
        ),
        None,
    )
    numbers = [re.sub(r"\D", "", chunk) for chunk in re.findall(r"\d[\d\s-]{4,}\d", text)]
    account = max(numbers, key=len, default="")
    return PaymentTarget(provider=provider, account_number=account, raw=text.strip())


def format_payment_info(provider_label: str, account_number: str, holder: str = "") -> str:
    parts = [provider_label.strip(), re.sub(r"[^\d]", "", account_number)]
    if holder.strip():
        parts.append(f"a.n. {holder.strip()}")
    return " ".join(part for part in parts if part)


def normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("0"):
        return "62" + digits[1:]
    if digits.startswith("8"):
        return "62" + digits
    return digits


def payment_reminder(debtor: str, creditor: str, amount: int, target: PaymentTarget) -> str:
    lines = [
        f"Halo {debtor}, ini pengingat dari KosSplit.",
        f"Kamu perlu membayar {rupiah(amount)} ke {creditor}.",
    ]
    if target.account_number:
        lines.append(f"Transfer ke {target.label}: {target.account_number}")
    elif target.raw:
        lines.append(f"Info pembayaran: {target.raw}")
    lines.append("Terima kasih.")
    return "\n".join(lines)


def whatsapp_url(phone: str, message: str) -> str:
    number = normalize_phone(phone)
    return f"https://wa.me/{number}?text={quote(message)}"
