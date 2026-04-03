from pathlib import Path
import re
import tkinter as tk

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


class UrlReviewGui:
	def __init__(self, raw_text: str):
		self.lines = raw_text.splitlines()
		self.occurrences = collect_url_occurrences(raw_text)
		self.accepted_urls: list[str] = []

		self.current_index = 0
		self.candidate = ""
		self.next_line_index = 0
		self.history: list[tuple[str, int]] = []
		self.preview_section = ""
		self.preview_next_index = 0

		self.root = tk.Tk()
		self.root.title("URL Reviewer")
		self.root.geometry("1100x420")
		self.root.minsize(900, 360)
		self.root.protocol("WM_DELETE_WINDOW", self.close)

		self.current_var = tk.StringVar()
		self.joined_var = tk.StringVar()
		self.status_var = tk.StringVar()

		container = tk.Frame(self.root, padx=16, pady=16)
		container.pack(fill="both", expand=True)

		title_label = tk.Label(container, text="Review detected URLs", font=("Segoe UI", 14, "bold"))
		title_label.pack(anchor="w", pady=(0, 10))

		panels = tk.Frame(container)
		panels.pack(fill="both", expand=True)

		left = tk.LabelFrame(panels, text="Current address", padx=12, pady=12)
		left.pack(side="left", fill="both", expand=True, padx=(0, 10))

		left_value = tk.Label(left, textvariable=self.current_var, justify="left", anchor="nw", wraplength=430)
		left_value.pack(fill="both", expand=True)

		accept_button = tk.Button(
			left,
			text="Accept current (1)",
			bg="#2E7D32",
			fg="white",
			activebackground="#1B5E20",
			font=("Segoe UI", 11, "bold"),
			command=self.accept_current,
		)
		accept_button.pack(fill="x", pady=(10, 0))

		right = tk.LabelFrame(panels, text="Address with next section", padx=12, pady=12)
		right.pack(side="left", fill="both", expand=True)

		right_value = tk.Label(right, textvariable=self.joined_var, justify="left", anchor="nw", wraplength=430)
		right_value.pack(fill="both", expand=True)

		join_button = tk.Button(
			right,
			text="Join next section (2)",
			bg="#C62828",
			fg="white",
			activebackground="#8E0000",
			font=("Segoe UI", 11, "bold"),
			command=self.join_next_section,
		)
		join_button.pack(fill="x", pady=(10, 0))

		footer = tk.Frame(container)
		footer.pack(fill="x", pady=(10, 0))

		revert_button = tk.Button(footer, text="Revert last action (r)", command=self.revert_last_action)
		revert_button.pack(side="left")

		status_label = tk.Label(footer, textvariable=self.status_var, anchor="w")
		status_label.pack(side="left", padx=(12, 0))

		self.root.bind("1", self.on_accept_key)
		self.root.bind("2", self.on_join_key)
		self.root.bind("r", self.on_revert_key)
		self.root.bind("R", self.on_revert_key)

	def find_next_section(self, start_index: int) -> tuple[str, int]:
		index = start_index
		while index < len(self.lines):
			continuation = scan_url_continuation_from_line(self.lines[index])
			index += 1
			if continuation:
				return continuation, index
		return "", len(self.lines)

	def load_occurrence(self) -> None:
		if self.current_index >= len(self.occurrences):
			self.status_var.set("Review complete. Close the window.")
			self.root.after(50, self.close)
			return

		entry = self.occurrences[self.current_index]
		self.candidate = str(entry["url"])
		self.next_line_index = int(entry["next_line_index"])
		self.history.clear()
		self.refresh_view()

	def refresh_view(self) -> None:
		self.preview_section, self.preview_next_index = self.find_next_section(self.next_line_index)

		self.current_var.set(self.candidate)
		if self.preview_section:
			joined_preview = strip_trailing_url_punctuation(self.candidate + self.preview_section)
			self.joined_var.set(joined_preview)
		else:
			self.joined_var.set("(No further section found)")

		reviewed = self.current_index + 1
		total = len(self.occurrences)
		self.status_var.set(f"Item {reviewed}/{total}")

	def accept_current(self) -> None:
		if self.candidate:
			self.accepted_urls.append(self.candidate)
		self.current_index += 1
		self.load_occurrence()

	def join_next_section(self) -> None:
		if not self.preview_section:
			self.status_var.set("No next section available to join.")
			return

		self.history.append((self.candidate, self.next_line_index))
		self.candidate = strip_trailing_url_punctuation(self.candidate + self.preview_section)
		self.next_line_index = self.preview_next_index
		self.refresh_view()

	def revert_last_action(self) -> None:
		if not self.history:
			self.status_var.set("Nothing to revert.")
			return

		self.candidate, self.next_line_index = self.history.pop()
		self.refresh_view()

	def on_accept_key(self, _event: tk.Event) -> str:
		self.accept_current()
		return "break"

	def on_join_key(self, _event: tk.Event) -> str:
		self.join_next_section()
		return "break"

	def on_revert_key(self, _event: tk.Event) -> str:
		self.revert_last_action()
		return "break"

	def close(self) -> None:
		self.root.quit()
		self.root.destroy()

	def run(self) -> list[str]:
		if not self.occurrences:
			self.root.after(50, self.close)
		else:
			self.load_occurrence()
		self.root.mainloop()
		return self.accepted_urls


def review_detected_urls(raw_text: str) -> list[str]:
	gui = UrlReviewGui(raw_text)
	return gui.run()


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

	print("Launching URL review GUI. Use 1=accept, 2=join next section, r=revert.")
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

