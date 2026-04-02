from pathlib import Path
import re

from pypdf import PdfReader


def flatten_text_preserving_wrapped_urls(text: str) -> str:
	parts: list[str] = []
	length = len(text)
	i = 0

	while i < length:
		char = text[i]
		if char not in "\r\n":
			parts.append(char)
			i += 1
			continue

		# Consume a full newline sequence (\r, \n, or \r\n).
		j = i
		while j < length and text[j] in "\r\n":
			j += 1

		left_text = "".join(parts)
		left_token_match = re.search(r"(\S+)$", left_text)
		left_token = left_token_match.group(1) if left_token_match else ""

		right_token_match = re.match(r"\s*(\S+)", text[j:])
		right_token = right_token_match.group(1) if right_token_match else ""

		left_has_url_start = (
			"http://" in left_token
			or "https://" in left_token
			or left_token.startswith("www.")
		)
		left_token_looks_incomplete = left_token.endswith(("-", "/", ".", "_", ":", "?", "&", "=", "%","dx","doi","10"))
		right_looks_like_url_continuation = bool(
			right_token and re.match(r"^[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+$", right_token)
		)

		if left_has_url_start and left_token_looks_incomplete and right_looks_like_url_continuation:
			# Keep wrapped URLs contiguous across line breaks.
			pass
		else:
			parts.append(" ")

		i = j

	return "".join(parts)


def main() -> None:
	import_dir = Path("./import")

	if not import_dir.exists() or not import_dir.is_dir():
		print("cancel")
		return

	files = [p for p in import_dir.iterdir() if p.is_file()]
	if len(files) != 1:
		print("cancel")
		return

	target_file = files[0]
	if target_file.suffix.lower() != ".pdf":
		print("cancel")
		return

	try:
		reader = PdfReader(str(target_file))
		text = "\n".join((page.extract_text() or "") for page in reader.pages)
	except Exception:
		print("cancel")
		return

	flat_text = flatten_text_preserving_wrapped_urls(text)
	links = re.findall(r"https?://\S+|www\.\S+", flat_text)

	if not links:
		print("cancel")
		return

	print("\n".join(links))


if __name__ == "__main__":
	main()

