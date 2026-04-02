from pypdf import PdfReader

preproc = True


if preproc:
    with open("import.txt", 'r+',encoding='utf-8') as f:
        x = f.read()
        x = x.replace("\n", " ")
        f.seek(0)
        f.write(x)
        x = x.replace("\n", " ")
        f.seek(0)
        f.write(x)
        x = x.replace("\n", " ")
        x = x.replace(". ", ".")
        x = x.replace(" .", ".")
        f.seek(0)
        f.write(x)


##print(x)

import re


# Regex: match dx.doi.org/ and all characters until a space followed by a capital letter and a lowercase letter (e.g., ' Ab')
doi_pattern = r'https?://dx\.doi\.org/.*?(?= [A-Z][a-z])'
doi_addresses = re.findall(doi_pattern, x)



doi_addresses = [doi.replace(' ', '') for doi in doi_addresses]
with open('results.txt', 'w', encoding='utf-8') as out:
    for doi in doi_addresses:
        out.write(doi + '\n')
print(f"{len(doi_addresses)} DOI links written to results.txt")
