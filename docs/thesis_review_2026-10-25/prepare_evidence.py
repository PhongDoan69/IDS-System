"""Read-only input audit; writes only this review package. No training or model selection."""
from pathlib import Path
import csv
import difflib
import hashlib
import json
import re
from collections import Counter

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
DOWNLOADS = Path(r'C:\Users\Admin\Downloads')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def entries(text):
    """Parse the braced entries/fields used in this supplied BibTeX file."""
    result = []
    for match in re.finditer(r'@(article|inproceedings|incollection)\s*\{\s*([^,]+),', text, re.I):
        depth, cursor = 1, match.end()
        while cursor < len(text) and depth:
            if text[cursor] in '{}':
                depth += 1 if text[cursor] == '{' else -1
            cursor += 1
        if depth:
            raise ValueError(f'Unbalanced entry: {match[2]}')
        body = text[match.end():cursor - 1]
        fields, offset = {}, 0
        while offset < len(body):
            f = re.search(r'([A-Za-z_]+)\s*=\s*\{', body[offset:])
            if not f:
                break
            start = offset + f.end()
            pos, level = start, 1
            while pos < len(body) and level:
                if body[pos] in '{}':
                    level += 1 if body[pos] == '{' else -1
                pos += 1
            if level:
                raise ValueError(f'Unbalanced field: {match[2]}/{f[1]}')
            fields[f[1].lower()] = body[start:pos - 1]
            offset = pos
        result.append({'key': match[2].strip(), 'type': match[1].lower(), 'fields': fields})
    return result


def main():
    evidence = ROOT / 'evidence'
    evidence.mkdir(exist_ok=True)
    bib_path = DOWNLOADS / 'references (2).bib'
    original = bib_path.read_text(encoding='utf-8-sig')
    parsed = entries(original)
    duplicates = [k for k, v in Counter(e['key'] for e in parsed).items() if v > 1]
    assert not duplicates
    redundant = [e['key'] for e in parsed if e['fields'].get('note', '').lower().strip() == 'doi: ' + e['fields'].get('doi', '').lower().strip()]
    corrected = re.sub(r',\s*\n\s*note\s*=\s*\{doi:\s*[^}]+\}', '', original, flags=re.I)
    old_url = 'https://openreview.net/references/pdf?id=HJ2Pfowdg'
    assert original.count(old_url) == 1
    corrected = corrected.replace(old_url, 'https://arxiv.org/abs/1610.02136')
    reparsed = entries(corrected)
    assert [e['key'] for e in parsed] == [e['key'] for e in reparsed]
    assert [e['fields'].get('doi') for e in parsed] == [e['fields'].get('doi') for e in reparsed]
    for old, new in zip(parsed, reparsed):
        expected = dict(old['fields'])
        if old['key'] in redundant:
            expected.pop('note')
        if old['key'] == 'hendrycks2017baseline':
            expected['url'] = 'https://arxiv.org/abs/1610.02136'
        assert new['fields'] == expected, old['key']
    (ROOT / 'references_reviewed.bib').write_text(corrected, encoding='utf-8')
    (evidence / 'references_original.bib').write_text(original, encoding='utf-8')
    (evidence / 'references_patch.diff').write_text(''.join(difflib.unified_diff(original.splitlines(True), corrected.splitlines(True), fromfile='references (2).bib', tofile='references_reviewed.bib')), encoding='utf-8')

    pages = json.loads((evidence / 'pdf_pages.json').read_text(encoding='utf-8'))
    body = '\n'.join(p['text'] for p in pages[7:104])
    cited = set()
    for group in re.findall(r'\[(\d+(?:\s*[,\-–]\s*\d+)*)\]', body):
        for part in group.split(','):
            bounds = re.split('[-–]', part)
            cited.update(range(int(bounds[0]), int(bounds[-1]) + 1))

    counts = {}
    with (REPO / 'results/split_summary.csv').open(encoding='utf-8-sig', newline='') as f:
        for row in csv.DictReader(f):
            k = int(row['attack_label_id'])
            counts.setdefault(k, {'label': row['attack_label']})[row['split']] = int(row['count'])
    totals = {s: sum(v[s] for v in counts.values()) for s in ('train', 'validation', 'test')}
    assert totals == {'train': 1467762, 'validation': 314521, 'test': 314521}
    table = ['| ID | Label | Train | Validation | Test | Total |', '|---:|---|---:|---:|---:|---:|']
    tex = [r'\begin{longtable}{r p{0.39\textwidth} r r r r}', r'\caption{Observed label counts in the existing exploratory split.}\label{tab:observed-label-counts}\\', r'\hline ID & Label & Train & Validation & Test & Total\\\hline', r'\endfirsthead', r'\hline ID & Label & Train & Validation & Test & Total\\\hline', r'\endhead']
    for k, v in sorted(counts.items()):
        n = sum(v[s] for s in totals)
        table.append(f"| {k} | {v['label']} | {v['train']:,} | {v['validation']:,} | {v['test']:,} | {n:,} |")
        label = v['label'].replace('&', r'\&').replace('_', r'\_').replace('%', r'\%')
        tex.append(f"{k} & {label} & {v['train']:,} & {v['validation']:,} & {v['test']:,} & {n:,}" + r'\\')
    tex += [r'\hline', r'\end{longtable}']
    (ROOT / 'CLASS_DISTRIBUTION.md').write_text('# Observed class distribution\n\nSource: `results/split_summary.csv`; existing exploratory split, not a new partition. `results/dataset_summary.csv` contains source-file summaries, not per-label counts.\n\n' + '\n'.join(table) + '\n', encoding='utf-8')
    (ROOT / 'class_distribution.tex').write_text('% Requires \\usepackage{longtable}; insert into the existing thesis project.\n' + '\n'.join(tex) + '\n', encoding='utf-8')

    upstream = []
    for p in sorted((ROOT / 'upstream').rglob('*')):
        if p.is_file():
            rel = p.relative_to(ROOT / 'upstream').as_posix()
            upstream.append({'path': rel, 'url': 'https://github.com/lishix520/academic-paper-skills/blob/main/' + rel, 'sha256_local_utf8': sha(p)})
    source_inputs = [DOWNLOADS / 'main (3).pdf', bib_path, REPO / 'results/split_summary.csv', REPO / 'results/dataset_summary.csv']
    report = {
        'review_date': '2026-10-25',
        'local_repo_head_at_review': '8e96ddd0aeff5605496eb884a2a81ab8d9ee64d4',
        'historical_audit_commit_cited_in_thesis': '895cc8bbba59497ceda625cf9947fa1828e20724',
        'inputs': [{'path': str(p), 'sha256': sha(p)} for p in source_inputs],
        'upstream': upstream, 'upstream_root_SKILL_exists': False,
        'upstream_ref': 'main fetched on review date; no immutable commit ID asserted',
        'pdf_pages': len(pages), 'bib_entries': len(parsed),
        'entry_types': dict(Counter(e['type'] for e in parsed)),
        'duplicate_keys': duplicates,
        'duplicate_dois': [k for k,v in Counter(e['fields'].get('doi','').lower() for e in parsed if e['fields'].get('doi')).items() if v>1],
        'years': dict(sorted(Counter(e['fields']['year'] for e in parsed).items())),
        'doi_count': sum('doi' in e['fields'] for e in parsed),
        'redundant_doi_notes_removed': redundant,
        'extracted_body_reference_numbers_in_range': sorted(n for n in cited if 1 <= n <= 29),
        'other_bracket_number_tokens_not_asserted_as_citations': sorted(n for n in cited if not 1 <= n <= 29),
        'numeric_reference_range': [1,29],
        'citation_check_limit': 'PDF-number coverage only; source LaTeX citation keys and semantic support not proven.',
        'split_totals': totals, 'class_count': len(counts),
        'benign_total': sum(counts[0][s] for s in totals),
        'benign_percent': 100*sum(counts[0][s] for s in totals)/sum(totals.values()),
        'source_PDF_unchanged': True, 'training_executed': False,
    }
    (evidence / 'input_audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ['inputs','upstream','redundant_doi_notes_removed']},ensure_ascii=False,indent=2))
    print('Redundant DOI notes removed:', len(redundant))


if __name__ == '__main__':
    main()
