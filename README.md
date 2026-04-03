# ZoteroPythonImport

GUI tool to extract, review, edit, and compare links from a PDF before exporting text files for Zotero workflows.
Highly specific.
Only semi automatic.
Use at your own risk lol.

## Requirements

- Python 3.10+
- `pypdf`
- `pdfx`
- Tkinter (usually included with standard Python on Windows)

Install dependencies:

```bash
pip install pypdf pdfx
```

## Project Layout

- `import/`: input folder, must contain exactly one PDF file.
- `main.py`: application entry point.
- `results.txt`: manually reviewed/edited links.
- `results_auto.txt`: automatically extracted links (pdfx mode).
- `results_merged.txt`: merge of manual + auto links.
- `result_dif.txt`: links in auto that are not in manual.
- `results_noDoi.txt`: exported non-DOI links from overview screen.

## Run

```bash
python main.py
```

At startup, a GUI mode picker appears.

## Startup Modes

1. Guided review
2. Extract embedded links (pdfx)
3. Edit existing `results.txt` (only shown when `results.txt` exists)
4. Merge `results.txt` + `results_auto.txt` (only shown when both exist)
5. Auto minus manual (`result_dif.txt`) (only shown when both exist)

### Mode Details

#### 1) Guided review

- Reads PDF text with `pypdf`.
- Shows a two-panel reviewer:
	- Left: current link candidate.
	- Right: candidate + next joined section preview.
- Controls:
	- Accept current: green button, key `1`
	- Join next section: red button, key `2`
	- Revert last join: key `r`
- After review, opens the final overview editor.
- Final output is saved to `results.txt`.

#### 2) Extract embedded links (pdfx)

- Uses `pdfx` (`get_metadata`, `get_references`, `get_references_as_dict`).
- Deduplicates while preserving order.
- Saves to `results_auto.txt`.

#### 3) Edit existing results

- Loads links from `results.txt`.
- Builds possible joined suggestions from the current PDF.
- Opens the final overview editor.
- Saves edited results back to `results.txt`.

#### 4) Merge manual + auto

- Combines `results.txt` and `results_auto.txt`.
- Removes duplicates while preserving order.
- Saves to `results_merged.txt`.

#### 5) Auto minus manual

- Subtracts manual links from auto links (`auto - manual`).
- Saves to `result_dif.txt`.

## Final Overview Editor

For each selected row:

- View `Accepted link` and `Possible joined link`.
- Edit `Final editable link`.
- Buttons:
	- Use accepted
	- Use suggested
	- Update suggestion
	- Delete link
	- Save row

Footer actions:

- Finish and continue
- Add `http://` to missing (bulk update all current final links)
- DOI filter export (writes links without `doi` to `results_noDoi.txt`)

Shortcuts:

- `Enter`: save row
- `Ctrl+S`: save row

## Notes

- If the overview window is closed without finishing, the run is treated as canceled.
- The app expects exactly one PDF in `import/`.
