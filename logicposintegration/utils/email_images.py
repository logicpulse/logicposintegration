import base64
from io import BytesIO
from urllib.parse import urlparse

import frappe
from frappe.core.doctype.file.utils import find_file_by_url, get_local_image, get_web_image
from frappe.utils import get_url, image_to_base64, safe_decode

DEFAULT_LOGO_URL = "https://www.logicpulse.com/images/thumbs/0002017.png"


def get_email_image_data_uri(src: str | None = None, max_height: int = 80) -> str:
	"""Embed an image as a data URI for HTML emails (avoids blocked remote images)."""
	src = src or DEFAULT_LOGO_URL
	if src.startswith("data:"):
		return src

	try:
		image, extn = _load_image(src)
		return _to_data_uri(image, extn, max_height)
	except Exception:
		frappe.log_error(title="Email image embed failed", message=frappe.get_traceback())
		return src


def _load_image(src: str):
	from PIL import Image

	path = _normalize_path(src)

	if path.startswith(("/files", "/private")):
		file_doc = find_file_by_url(path)
		if file_doc:
			content = file_doc.get_content()
			image = Image.open(BytesIO(content))
			extn = _extension_from_path(path)
			return image, extn

		image, _filename, extn = get_local_image(path)
		return image, extn

	web_src = src if src.startswith("http") else get_url(path)
	image, _filename, extn = get_web_image(web_src)
	return image, extn


def _normalize_path(src: str) -> str:
	if not src.startswith("http"):
		return src

	parsed = urlparse(src)
	site = urlparse(get_url())
	if parsed.netloc and parsed.netloc == site.netloc:
		return parsed.path
	return src


def _extension_from_path(path: str) -> str:
	extn = path.rsplit(".", 1)[-1].lower() if "." in path else "png"
	if extn in ("jpg", "jpe"):
		return "JPEG"
	return extn.upper()


def _to_data_uri(image, extn: str, max_height: int) -> str:
	from PIL import Image

	if max_height and image.height > max_height:
		image = image.copy()
		image.thumbnail((int(image.width * max_height / image.height), max_height), Image.Resampling.LANCZOS)

	save_extn = "JPEG" if extn.upper() in ("JPG", "JPE", "JPEG") else extn.upper()
	b64 = safe_decode(image_to_base64(image, save_extn))
	mime = "image/jpeg" if save_extn == "JPEG" else f"image/{save_extn.lower()}"
	return f"data:{mime};base64,{b64}"
