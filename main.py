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
		left_token_looks_incomplete = left_token.endswith(("-", "/", ".", "_", ":", "?", "&", "=", "%"))
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


def strip_trailing_url_punctuation(url: str) -> str:
	return url.rstrip(").,;:!?'\"]")


def scan_url_continuation_from_line(line: str) -> str:
	match = re.match(r"\s*([A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+)", line)
	if not match:
		return ""
	return match.group(1)


def review_detected_urls(raw_text: str) -> list[str]:
	lines = raw_text.splitlines()
	accepted_urls: list[str] = []

	for line_index, line in enumerate(lines):
		for match in re.finditer(r"https?://\S+|www\.\S+", line):
			candidate = strip_trailing_url_punctuation(match.group(0))
			next_line_index = line_index + 1

			while True:
				print(f"\nDetected URL: {candidate}")
				decision = input("Press Enter if correct, any other key then Enter for incomplete: ")

				if decision == "":
					if candidate:
						accepted_urls.append(candidate)
					break

				if next_line_index >= len(lines):
					print("No more lines to scan for continuation.")
					break

				continuation = scan_url_continuation_from_line(lines[next_line_index])
				next_line_index += 1

				if not continuation:
					print("No URL-like continuation found on next line.")
					continue

				candidate = strip_trailing_url_punctuation(candidate + continuation)

	return accepted_urls


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
	if not re.search(r"https?://\S+|www\.\S+", flat_text):
		print("cancel")
		return

	print("Review each detected URL. Use Enter to accept, or type anything to mark incomplete.")
	links = review_detected_urls(text)

	if not links:
		print("cancel")
		return

	print("\nAccepted URLs:")
	print("\n".join(links))


if __name__ == "__main__":
	main()

