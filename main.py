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
			history: list[str] = []

			while True:
				print(f"\nDetected URL: {candidate}")
				decision = input("Press Enter if correct, type 'r' to revert last change, any other key then Enter for incomplete: ")

				if decision == "":
					if candidate:
						accepted_urls.append(candidate)
					break

				if decision.lower() == "r":
					if history:
						candidate = history.pop()
					else:
						print("Nothing to revert.")
					continue

				if next_line_index >= len(lines):
					print("No more lines to scan for continuation.")
					break

				continuation = scan_url_continuation_from_line(lines[next_line_index])
				next_line_index += 1

				if not continuation:
					print("No URL-like continuation found on next line.")
					continue

				history.append(candidate)
				candidate = strip_trailing_url_punctuation(candidate + continuation)

	return accepted_urls


def collect_detected_urls(flat_text: str) -> list[str]:
	raw_links = re.findall(r"https?://\S+|www\.\S+", flat_text)
	return [strip_trailing_url_punctuation(link) for link in raw_links if strip_trailing_url_punctuation(link)]


def collect_url_occurrences(raw_text: str) -> list[dict[str, int | str]]:
	occurrences: list[dict[str, int | str]] = []
	lines = raw_text.splitlines()

	for line_index, line in enumerate(lines):
		for match in re.finditer(r"https?://\S+|www\.\S+", line):
			url = strip_trailing_url_punctuation(match.group(0))
			if not url:
				continue
			occurrences.append({"url": url, "next_line_index": line_index + 1})

	return occurrences


def has_duplicates(urls: list[str]) -> bool:
	return len(urls) != len(set(urls))


def resolve_duplicate_urls_with_more_lines(raw_text: str, max_rounds: int = 8) -> list[str]:
	lines = raw_text.splitlines()
	occurrences = collect_url_occurrences(raw_text)

	if not occurrences:
		return []

	for _ in range(max_rounds):
		urls = [str(entry["url"]) for entry in occurrences]
		if not has_duplicates(urls):
			return urls

		counts: dict[str, int] = {}
		for url in urls:
			counts[url] = counts.get(url, 0) + 1

		duplicate_urls = {url for url, count in counts.items() if count > 1}
		progress_made = False

		for entry in occurrences:
			current_url = str(entry["url"])
			if current_url not in duplicate_urls:
				continue

			next_line_index = int(entry["next_line_index"])
			if next_line_index >= len(lines):
				continue

			continuation = scan_url_continuation_from_line(lines[next_line_index])
			entry["next_line_index"] = next_line_index + 1

			if not continuation:
				continue

			entry["url"] = strip_trailing_url_punctuation(current_url + continuation)
			progress_made = True

		if not progress_made:
			break

	return [str(entry["url"]) for entry in occurrences]


def main() -> None:
	import_dir = Path("./import")

	if not import_dir.exists() or not import_dir.is_dir():
		print("cancel no dir")
		return

	files = [p for p in import_dir.iterdir() if p.is_file()]
	if len(files) != 1:
		print("cancel file count")
		return

	target_file = files[0]
	if target_file.suffix.lower() != ".pdf":
		print("cancel not pdf")
		return

	try:
		reader = PdfReader(str(target_file))
		text = "\n".join((page.extract_text() or "") for page in reader.pages)
	except Exception:
		print("cancel pdf extraction")
		return

	flat_text = flatten_text_preserving_wrapped_urls(text)
	detected_links = collect_detected_urls(flat_text)
	if not detected_links:
		print("cancel no urls found")
		return

	if has_duplicates(detected_links):
		detected_links = resolve_duplicate_urls_with_more_lines(text)
		if not detected_links or has_duplicates(detected_links):
			print("cancel")
			return

	print("Review each detected URL. Use Enter to accept, 'r' to revert last change, or type anything to mark incomplete.")
	links = review_detected_urls(text)

	if not links:
		print("cancel")
		return

	results_file = Path("results.txt")
	results_file.write_text("\n".join(links) + "\n", encoding="utf-8")

	print("\nAccepted URLs:")
	print("\n".join(links))
	print(f"\nSaved to {results_file}")


if __name__ == "__main__":
	main()

