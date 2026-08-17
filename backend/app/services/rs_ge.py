"""Revenue Service (RS.ge) WayBill SOAP client."""
from __future__ import annotations

from typing import Any
from xml.etree import ElementTree as ET

import httpx

SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/"
TEMPURI_NS = "http://tempuri.org/"


class RSGeError(RuntimeError):
    pass


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _xml_to_data(element: ET.Element) -> Any:
    children = list(element)
    if not children:
        return (element.text or "").strip()
    result: dict[str, Any] = {}
    for child in children:
        key = _local_name(child.tag)
        value = _xml_to_data(child)
        if key in result:
            if not isinstance(result[key], list):
                result[key] = [result[key]]
            result[key].append(value)
        else:
            result[key] = value
    return result


class RSGeClient:
    def __init__(self, url: str, service_user: str = "", service_password: str = ""):
        self.url = url
        self.service_user = service_user
        self.service_password = service_password

    async def _post(self, operation: str, params: dict[str, Any] | None = None) -> ET.Element:
        envelope = ET.Element(ET.QName(SOAP_NS, "Envelope"))
        body = ET.SubElement(envelope, ET.QName(SOAP_NS, "Body"))
        request = ET.SubElement(body, ET.QName(TEMPURI_NS, operation))
        for key, value in (params or {}).items():
            child = ET.SubElement(request, ET.QName(TEMPURI_NS, key))
            child.text = str(value)
        payload = ET.tostring(envelope, encoding="utf-8", xml_declaration=True)
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    self.url,
                    content=payload,
                    headers={
                        "Content-Type": "text/xml; charset=utf-8",
                        "SOAPAction": f'"{TEMPURI_NS}{operation}"',
                    },
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RSGeError("RS.ge სერვერთან კავშირი ვერ დამყარდა") from exc
        try:
            root = ET.fromstring(response.content)
        except ET.ParseError as exc:
            raise RSGeError("RS.ge სერვერმა არასწორი XML დააბრუნა") from exc
        fault = root.find(f".//{{{SOAP_NS}}}Fault")
        if fault is not None:
            fault_text = fault.findtext("faultstring") or "RS.ge SOAP შეცდომა"
            raise RSGeError(fault_text)
        result = next((node for node in root.iter() if _local_name(node.tag) == f"{operation}Result"), None)
        if result is None:
            raise RSGeError("RS.ge პასუხში შედეგი ვერ მოიძებნა")
        return result

    async def get_server_time(self) -> str:
        return str(_xml_to_data(await self._post("get_server_time")))

    async def check_service_user(self) -> bool:
        result = _xml_to_data(await self._post("chek_service_user", {"su": self.service_user, "sp": self.service_password}))
        return str(result).strip().lower() in {"true", "1"}

    async def get_waybill_by_number(self, waybill_number: str) -> dict[str, Any]:
        result = await self._post("get_waybill_by_number", {"su": self.service_user, "sp": self.service_password, "waybill_number": waybill_number})
        data = _xml_to_data(result)
        return data if isinstance(data, dict) else {"value": data}

    async def submit_invoice(self, invoice_number: str, buyer_id: str, issue_date: str, total: str, vat: str) -> dict[str, Any]:
        """Submit an invoice (ანგარიშ-ფაქტურა) to RS.ge."""
        result = await self._post("submit_invoice", {
            "su": self.service_user, "sp": self.service_password,
            "invoice_number": invoice_number, "buyer_id": buyer_id,
            "issue_date": issue_date, "total": total, "vat": vat,
        })
        data = _xml_to_data(result)
        return data if isinstance(data, dict) else {"value": data}

    async def submit_waybill(self, waybill_number: str, sender_id: str, receiver_id: str, issue_date: str, total: str) -> dict[str, Any]:
        """Submit a waybill (ზედნადები) to RS.ge."""
        result = await self._post("submit_waybill", {
            "su": self.service_user, "sp": self.service_password,
            "waybill_number": waybill_number, "sender_id": sender_id,
            "receiver_id": receiver_id, "issue_date": issue_date, "total": total,
        })
        data = _xml_to_data(result)
        return data if isinstance(data, dict) else {"value": data}

    async def export_declaration(self, period: str, declaration_type: str) -> dict[str, Any]:
        """Export a tax declaration (VAT / income tax) for a period."""
        result = await self._post("export_declaration", {
            "su": self.service_user, "sp": self.service_password,
            "period": period, "declaration_type": declaration_type,
        })
        data = _xml_to_data(result)
        return data if isinstance(data, dict) else {"value": data}
