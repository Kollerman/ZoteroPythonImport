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


def ensure_http_prefix(url: str) -> str:
	cleaned = strip_trailing_url_punctuation(url.strip())
	if not cleaned:
		return ""
	lower = cleaned.lower()
	if lower.startswith("http://") or lower.startswith("https://"):
		return cleaned
	return f"http://{cleaned}"


def scan_url_continuation_from_line(line: str) -> str:
	match = re.match(r"\s*([A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+)", line)
	if not match:
		return ""
	return match.group(1)


def find_next_section(lines: list[str], start_index: int) -> tuple[str, int]:
	index = start_index
	while index < len(lines):
		continuation = scan_url_continuation_from_line(lines[index])
		index += 1
		if continuation:
			return continuation, index
	return "", len(lines)


class UrlReviewGui:
	def __init__(self, raw_text: str):
		self.raw_text = raw_text
		self.lines = raw_text.splitlines()
		self.occurrences = collect_url_occurrences(raw_text)
		self.accepted_records: list[dict[str, str]] = []

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
		return find_next_section(self.lines, start_index)

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
			suggestion = ""
			if self.preview_section:
				suggestion = strip_trailing_url_punctuation(self.candidate + self.preview_section)
			self.accepted_records.append(
				{
					"accepted": self.candidate,
					"suggested": suggestion,
					"final": self.candidate,
				}
			)
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

		if not self.accepted_records:
			return []

		editor = FinalLinksEditorGui(self.accepted_records, raw_text=self.raw_text)
		return editor.run()


class FinalLinksEditorGui:
	def __init__(self, records: list[dict[str, str]], raw_text: str | None = None):
		self.records = records
		self.done = False
		self.lines: list[str] = []
		self.occurrences: list[dict[str, int | str]] = []
		if raw_text:
			self.lines = raw_text.splitlines()
			self.occurrences = collect_url_occurrences(raw_text)

		self.root = tk.Tk()
		self.root.title("Accepted Links Overview")
		self.root.geometry("1200x620")
		self.root.minsize(1000, 520)
		self.root.protocol("WM_DELETE_WINDOW", self.close)

		container = tk.Frame(self.root, padx=16, pady=16)
		container.pack(fill="both", expand=True)

		title = tk.Label(
			container,
			text="Overview of accepted links, possible joined links, and final editable values",
			font=("Segoe UI", 13, "bold"),
		)
		title.pack(anchor="w", pady=(0, 10))

		body = tk.Frame(container)
		body.pack(fill="both", expand=True)

		left = tk.LabelFrame(body, text="Accepted items", padx=10, pady=10)
		left.pack(side="left", fill="both", expand=True, padx=(0, 10))

		self.listbox = tk.Listbox(left)
		self.listbox.pack(fill="both", expand=True)
		self.listbox.bind("<<ListboxSelect>>", self.on_select_row)

		right = tk.LabelFrame(body, text="Selected item details", padx=10, pady=10)
		right.pack(side="left", fill="both", expand=True)

		self.accepted_var = tk.StringVar()
		self.suggested_var = tk.StringVar()
		self.final_var = tk.StringVar()
		self.status_var = tk.StringVar()

		tk_accepted_label = tk.Label(right, text="Accepted link", anchor="w", font=("Segoe UI", 10, "bold"))
		tk_accepted_label.pack(fill="x")
		tk_accepted_value = tk.Label(right, textvariable=self.accepted_var, justify="left", anchor="w", wraplength=520)
		tk_accepted_value.pack(fill="x", pady=(2, 8))

		tk_suggested_label = tk.Label(right, text="Possible joined link", anchor="w", font=("Segoe UI", 10, "bold"))
		tk_suggested_label.pack(fill="x")
		tk_suggested_value = tk.Label(right, textvariable=self.suggested_var, justify="left", anchor="w", wraplength=520)
		tk_suggested_value.pack(fill="x", pady=(2, 8))

		final_label = tk.Label(right, text="Final editable link", anchor="w", font=("Segoe UI", 10, "bold"))
		final_label.pack(fill="x")
		final_entry = tk.Entry(right, textvariable=self.final_var)
		final_entry.pack(fill="x", pady=(2, 8))

		row_actions = tk.Frame(right)
		row_actions.pack(fill="x")

		use_accepted_btn = tk.Button(row_actions, text="Use accepted", command=self.use_accepted)
		use_accepted_btn.pack(side="left")

		use_suggested_btn = tk.Button(row_actions, text="Use suggested", command=self.use_suggested)
		use_suggested_btn.pack(side="left", padx=(8, 0))

		update_suggestion_btn = tk.Button(row_actions, text="Update suggestion", command=self.update_suggestion)
		update_suggestion_btn.pack(side="left", padx=(8, 0))

		delete_row_btn = tk.Button(row_actions, text="Delete link", bg="#B71C1C", fg="white", command=self.delete_current_row)
		delete_row_btn.pack(side="left", padx=(8, 0))

		save_row_btn = tk.Button(row_actions, text="Save row", command=self.save_current_row)
		save_row_btn.pack(side="left", padx=(8, 0))

		footer = tk.Frame(container)
		footer.pack(fill="x", pady=(10, 0))

		finish_btn = tk.Button(
			footer,
			text="Finish and continue",
			bg="#2E7D32",
			fg="white",
			activebackground="#1B5E20",
			font=("Segoe UI", 10, "bold"),
			command=self.finish,
		)
		finish_btn.pack(side="left")

		add_http_btn = tk.Button(footer, text="Add http:// to missing", command=self.add_http_to_all_links)
		add_http_btn.pack(side="left", padx=(8, 0))

		doi_filter_btn = tk.Button(footer, text="DOI filter export", command=self.export_no_doi_links)
		doi_filter_btn.pack(side="left", padx=(8, 0))

		status_label = tk.Label(footer, textvariable=self.status_var, anchor="w")
		status_label.pack(side="left", padx=(12, 0))

		self.root.bind("<Control-s>", self.on_ctrl_s)
		self.root.bind("<Return>", self.on_enter)

		self.populate_rows()

	def row_text(self, index: int) -> str:
		record = self.records[index]
		accepted = record["accepted"]
		final = record["final"]
		marker = "*" if final != accepted else " "
		return f"{index + 1:03d}{marker} {final}"

	def populate_rows(self) -> None:
		self.listbox.delete(0, tk.END)
		for idx in range(len(self.records)):
			self.listbox.insert(tk.END, self.row_text(idx))

		if self.records:
			self.listbox.selection_set(0)
			self.show_row(0)

	def selected_index(self) -> int | None:
		selection = self.listbox.curselection()
		if not selection:
			return None
		return int(selection[0])

	def show_row(self, index: int) -> None:
		record = self.records[index]
		self.accepted_var.set(record["accepted"])
		self.suggested_var.set(record["suggested"] or "(No suggestion available)")
		self.final_var.set(record["final"])
		self.status_var.set(f"Editing item {index + 1}/{len(self.records)}")

	def on_select_row(self, _event: tk.Event) -> None:
		idx = self.selected_index()
		if idx is None:
			return
		self.show_row(idx)

	def save_current_row(self) -> None:
		idx = self.selected_index()
		if idx is None:
			self.status_var.set("Select a row first.")
			return

		new_value = strip_trailing_url_punctuation(self.final_var.get().strip())
		if not new_value:
			self.status_var.set("Final link cannot be empty.")
			return

		self.records[idx]["final"] = new_value
		self.listbox.delete(idx)
		self.listbox.insert(idx, self.row_text(idx))
		self.listbox.selection_clear(0, tk.END)
		self.listbox.selection_set(idx)
		self.status_var.set(f"Saved item {idx + 1}.")

	def delete_current_row(self) -> None:
		idx = self.selected_index()
		if idx is None:
			self.status_var.set("Select a row first.")
			return

		del self.records[idx]
		self.populate_rows()
		if not self.records:
			self.accepted_var.set("")
			self.suggested_var.set("")
			self.final_var.set("")
			self.status_var.set("All links deleted.")
			return

		next_idx = min(idx, len(self.records) - 1)
		self.listbox.selection_clear(0, tk.END)
		self.listbox.selection_set(next_idx)
		self.show_row(next_idx)
		self.status_var.set(f"Deleted item {idx + 1}.")

	def use_accepted(self) -> None:
		idx = self.selected_index()
		if idx is None:
			return
		self.final_var.set(self.records[idx]["accepted"])

	def use_suggested(self) -> None:
		idx = self.selected_index()
		if idx is None:
			return
		suggested = self.records[idx]["suggested"]
		if not suggested:
			self.status_var.set("No suggestion available for this item.")
			return
		self.final_var.set(suggested)

	def update_suggestion(self) -> None:
		idx = self.selected_index()
		if idx is None:
			self.status_var.set("Select a row first.")
			return

		base_link = strip_trailing_url_punctuation(self.final_var.get().strip())
		if not base_link:
			self.status_var.set("Enter a link before updating suggestion.")
			return

		if not self.lines or not self.occurrences:
			self.status_var.set("No PDF context available for suggestion update.")
			return

		suggestion = build_suggestion_for_link(base_link, self.lines, self.occurrences)
		self.records[idx]["accepted"] = base_link
		self.records[idx]["final"] = base_link
		self.records[idx]["suggested"] = suggestion
		self.accepted_var.set(base_link)
		self.suggested_var.set(suggestion or "(No suggestion available)")
		self.listbox.delete(idx)
		self.listbox.insert(idx, self.row_text(idx))
		self.listbox.selection_clear(0, tk.END)
		self.listbox.selection_set(idx)
		if suggestion:
			self.status_var.set("Suggestion updated.")
		else:
			self.status_var.set("No new suggestion found for this link.")

	def add_http_to_all_links(self) -> None:
		if not self.records:
			self.status_var.set("No links to update.")
			return

		changed_count = 0
		for record in self.records:
			original = str(record["final"])
			updated = ensure_http_prefix(original)
			if updated and updated != original:
				record["final"] = updated
				changed_count += 1

		self.populate_rows()
		idx = self.selected_index()
		if idx is None and self.records:
			self.listbox.selection_set(0)
			self.show_row(0)
		elif idx is not None:
			self.show_row(idx)

		self.status_var.set(f"Added http:// to {changed_count} link(s).")

	def export_no_doi_links(self) -> None:
		if not self.records:
			self.status_var.set("No links to export.")
			return

		current_links = [str(record["final"]).strip() for record in self.records if str(record["final"]).strip()]
		output_file = Path("results_noDoi.txt")
		filtered_links = export_links_without_doi(current_links, output_file)
		if not filtered_links:
			self.status_var.set("No non-DOI links found.")
			return

		self.status_var.set(f"Exported {len(filtered_links)} non-DOI link(s) to {output_file}.")

	def finish(self) -> None:
		idx = self.selected_index()
		if idx is not None:
			self.save_current_row()

		self.done = True
		self.close()

	def on_ctrl_s(self, _event: tk.Event) -> str:
		self.save_current_row()
		return "break"

	def on_enter(self, _event: tk.Event) -> str:
		self.save_current_row()
		return "break"

	def close(self) -> None:
		self.root.quit()
		self.root.destroy()

	def run(self) -> list[str]:
		self.root.mainloop()
		if not self.done:
			return []
		return [record["final"] for record in self.records if record["final"]]


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


def read_existing_results(results_file: Path) -> list[str]:
	if not results_file.exists() or not results_file.is_file():
		return []

	text = results_file.read_text(encoding="utf-8", errors="ignore")
	return [line.strip() for line in text.splitlines() if line.strip()]


def build_suggestion_for_link(link: str, lines: list[str], occurrences: list[dict[str, int | str]]) -> str:
	for occurrence in occurrences:
		current = str(occurrence["url"])
		next_line_index = int(occurrence["next_line_index"])

		if not link.startswith(current):
			continue

		while True:
			if current == link:
				next_section, _ = find_next_section(lines, next_line_index)
				if not next_section:
					return ""
				return strip_trailing_url_punctuation(current + next_section)

			next_section, new_next_line_index = find_next_section(lines, next_line_index)
			if not next_section:
				break

			extended = strip_trailing_url_punctuation(current + next_section)
			if not link.startswith(extended):
				break

			current = extended
			next_line_index = new_next_line_index

	return ""


def build_records_from_links(links: list[str], raw_text: str) -> list[dict[str, str]]:
	lines = raw_text.splitlines()
	occurrences = collect_url_occurrences(raw_text)
	records: list[dict[str, str]] = []

	for link in links:
		suggestion = build_suggestion_for_link(link, lines, occurrences)
		records.append({"accepted": link, "suggested": suggestion, "final": link})

	return records


def unique_preserve_order(urls: list[str]) -> list[str]:
	seen: set[str] = set()
	unique_urls: list[str] = []
	for url in urls:
		if url in seen:
			continue
		seen.add(url)
		unique_urls.append(url)
	return unique_urls


def extract_links_with_pdfx(pdf_path: Path) -> list[str]:
	try:
		import pdfx  # type: ignore
	except Exception:
		return []

	try:
		pdf = pdfx.PDFx(str(pdf_path))
		# Follow the library's documented call sequence.
		pdf.get_metadata()
		raw_references = pdf.get_references()
		raw_references_dict = pdf.get_references_as_dict()
	except Exception:
		return []

	reference_values: list[str] = []

	if isinstance(raw_references, (list, tuple, set)):
		for item in raw_references:
			if isinstance(item, str):
				reference_values.append(item)

	if isinstance(raw_references_dict, dict):
		for value in raw_references_dict.values():
			if isinstance(value, str):
				reference_values.append(value)
			elif isinstance(value, (list, tuple, set)):
				for item in value:
					if isinstance(item, str):
						reference_values.append(item)

	normalized: list[str] = []
	for reference in reference_values:
		cleaned = strip_trailing_url_punctuation(reference.strip())
		if cleaned:
			normalized.append(cleaned)

	return unique_preserve_order(normalized)


def write_results(results_file: Path, links: list[str]) -> None:
	results_file.write_text("\n".join(links) + "\n", encoding="utf-8")


def export_links_without_doi(links: list[str], output_file: Path) -> list[str]:
	filtered = [link for link in links if "doi" not in link.lower()]
	filtered = unique_preserve_order(filtered)
	if filtered:
		write_results(output_file, filtered)
	return filtered


def merge_result_files(manual_file: Path, auto_file: Path, merged_file: Path) -> list[str]:
	manual_links = read_existing_results(manual_file)
	auto_links = read_existing_results(auto_file)
	merged_links = unique_preserve_order(manual_links + auto_links)
	if merged_links:
		write_results(merged_file, merged_links)
	return merged_links


def subtract_manual_from_auto(manual_file: Path, auto_file: Path, diff_file: Path) -> list[str]:
	manual_links = set(read_existing_results(manual_file))
	auto_links = read_existing_results(auto_file)
	diff_links = [link for link in auto_links if link not in manual_links]
	diff_links = unique_preserve_order(diff_links)
	if diff_links:
		write_results(diff_file, diff_links)
	return diff_links


def pick_mode_gui(has_existing_results: bool, has_existing_auto_results: bool) -> str:
	selection = {"mode": "cancel"}

	root = tk.Tk()
	root.title("Choose Startup Mode")
	root.geometry("560x300")
	root.minsize(520, 260)

	def select_mode(mode: str) -> None:
		selection["mode"] = mode
		root.quit()
		root.destroy()

	def cancel() -> None:
		selection["mode"] = "cancel"
		root.quit()
		root.destroy()

	root.protocol("WM_DELETE_WINDOW", cancel)

	container = tk.Frame(root, padx=16, pady=16)
	container.pack(fill="both", expand=True)

	title = tk.Label(container, text="How should this run start?", font=("Segoe UI", 14, "bold"))
	title.pack(anchor="w", pady=(0, 10))

	description = tk.Label(
		container,
		text="Select one mode. You can use buttons or keyboard shortcuts.",
		anchor="w",
	)
	description.pack(anchor="w", pady=(0, 10))

	button_area = tk.Frame(container)
	button_area.pack(fill="x")

	review_btn = tk.Button(
		button_area,
		text="1. Guided review",
		bg="#2E7D32",
		fg="white",
		activebackground="#1B5E20",
		font=("Segoe UI", 10, "bold"),
		command=lambda: select_mode("review"),
	)
	review_btn.pack(fill="x", pady=(0, 8))

	pdfx_btn = tk.Button(
		button_area,
		text="2. Extract embedded links (pdfx)",
		bg="#1565C0",
		fg="white",
		activebackground="#0D47A1",
		font=("Segoe UI", 10, "bold"),
		command=lambda: select_mode("pdfx"),
	)
	pdfx_btn.pack(fill="x", pady=(0, 8))

	if has_existing_results:
		edit_btn = tk.Button(
			button_area,
			text="3. Edit existing results.txt",
			bg="#6A1B9A",
			fg="white",
			activebackground="#4A148C",
			font=("Segoe UI", 10, "bold"),
			command=lambda: select_mode("edit"),
		)
		edit_btn.pack(fill="x", pady=(0, 8))

	if has_existing_results and has_existing_auto_results:
		merge_btn = tk.Button(
			button_area,
			text="4. Merge results.txt + results_auto.txt",
			bg="#EF6C00",
			fg="white",
			activebackground="#E65100",
			font=("Segoe UI", 10, "bold"),
			command=lambda: select_mode("merge"),
		)
		merge_btn.pack(fill="x", pady=(0, 8))

	if has_existing_results and has_existing_auto_results:
		diff_btn = tk.Button(
			button_area,
			text="5. Auto minus manual (result_dif.txt)",
			bg="#00897B",
			fg="white",
			activebackground="#00695C",
			font=("Segoe UI", 10, "bold"),
			command=lambda: select_mode("diff"),
		)
		diff_btn.pack(fill="x", pady=(0, 8))

	cancel_btn = tk.Button(button_area, text="Cancel (Esc)", command=cancel)
	cancel_btn.pack(fill="x")

	root.bind("1", lambda _event: select_mode("review"))
	root.bind("2", lambda _event: select_mode("pdfx"))
	if has_existing_results:
		root.bind("3", lambda _event: select_mode("edit"))
	if has_existing_results and has_existing_auto_results:
		root.bind("4", lambda _event: select_mode("merge"))
	if has_existing_results and has_existing_auto_results:
		root.bind("5", lambda _event: select_mode("diff"))
	root.bind("<Escape>", lambda _event: cancel())

	root.mainloop()
	return str(selection["mode"])


def main() -> None:
	import_dir = Path("./import")
	results_file = Path("results.txt")
	results_auto_file = Path("results_auto.txt")
	results_merged_file = Path("results_merged.txt")
	result_dif_file = Path("result_dif.txt")

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

	existing_links = read_existing_results(results_file)
	existing_auto_links = read_existing_results(results_auto_file)
	mode = pick_mode_gui(
		has_existing_results=bool(existing_links),
		has_existing_auto_results=bool(existing_auto_links),
	)
	if mode == "cancel":
		print("cancel")
		return

	if mode == "pdfx":
		links = extract_links_with_pdfx(target_file)
		if not links:
			print("cancel pdfx no links found")
			return

		write_results(results_auto_file, links)
		print("\nExtracted URLs (pdfx):")
		print("\n".join(links))
		print(f"\nSaved to {results_auto_file}")
		return

	if mode == "merge":
		merged_links = merge_result_files(results_file, results_auto_file, results_merged_file)
		if not merged_links:
			print("cancel merge no links found")
			return

		print("\nMerged URLs:")
		print("\n".join(merged_links))
		print(f"\nSaved to {results_merged_file}")
		return

	if mode == "diff":
		diff_links = subtract_manual_from_auto(results_file, results_auto_file, result_dif_file)
		if not diff_links:
			print("cancel diff no links found")
			return

		print("\nDifference URLs (auto - manual):")
		print("\n".join(diff_links))
		print(f"\nSaved to {result_dif_file}")
		return

	try:
		reader = PdfReader(str(target_file))
		text = "\n".join((page.extract_text() or "") for page in reader.pages)
	except Exception:
		print("cancel pdf extraction")
		return

	if existing_links and mode == "edit":
			records = build_records_from_links(existing_links, text)
			links = FinalLinksEditorGui(records, raw_text=text).run()

			if not links:
				print("cancel")
				return

			write_results(results_file, links)
			print("\nFinal URLs:")
			print("\n".join(links))
			print(f"\nSaved to {results_file}")
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

	write_results(results_file, links)

	print("\nAccepted URLs:")
	print("\n".join(links))
	print(f"\nSaved to {results_file}")


if __name__ == "__main__":
	main()

