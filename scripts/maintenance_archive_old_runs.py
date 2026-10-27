"""One-time audited cleanup: plan/archive only. Deletion is separate PowerShell."""
from pathlib import Path
import argparse
import hashlib
import json
import zipfile
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
OLD = ['main', 'loaco_26', 'round1_20261026_s42_main', 'round1_20261026_s42_loaco26',
       'cicunsw_r1_main', 'cicunsw_r2_20261026_iofix_main',
       'loaco_more_v2_20261027_h9_s42_regularized', 'loaco_more_v2_20261027_h25_s42_regularized']


def inside(path, directory):
    return path == directory or directory in path.parents


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive-dir')
    a = p.parse_args()
    candidates = [ROOT/'data/processed'/name for name in ['round1_20261026_s42', 'cicunsw_r1', 'cicunsw_r2_20261026_iofix']]
    candidates += [ROOT/'data/processed/experiments'/name for name in ['main', 'loaco_26']]
    candidates += [ROOT/'data/processed/round2_20261027_fp32_s42/experiments'/name for name in
                   ['loaco_more_v1_h9_s42_baseline', 'loaco_more_v2_20261027_h9_s42_regularized',
                    'loaco_more_v2_20261027_h25_s42_regularized']]
    for area in ['models', 'results']:
        for phase in ['autoencoder', 'stage1', 'stage2', 'novelty']:
            candidates += [ROOT/area/phase/name for name in OLD]
    pipeline = ROOT/'results/pipeline'
    candidates += [d for d in pipeline.iterdir() if d.is_dir() and
                   (d.name.startswith(('round1_20261026_s42_', 'cicunsw_r2_20261026_iofix_', 'eval_main_')) or d.name == 'loaco_26')]
    candidates = sorted(set(d.resolve() for d in candidates if d.is_dir()))
    for d in candidates:
        if not inside(d, ROOT) or d == ROOT or not any(inside(d, ROOT/x) for x in ['models', 'results', 'data/processed']):
            raise RuntimeError(f'Unsafe target: {d}')
    # Never retire a parent required by a retained executable artifact contract.
    blockers = []
    for area in ['data/processed', 'results', 'artifacts', 'models']:
        for f in (ROOT/area).rglob('*.json'):
            if f.name != 'contract.json' and not f.name.endswith('.contract.json'):
                continue
            if any(inside(f, d) for d in candidates):
                continue
            record = json.loads(f.read_text(encoding='utf-8'))
            for parent in record.get('parents', []):
                path = Path(parent['path']).resolve()
                if any(inside(path, d) for d in candidates):
                    blockers.append({'retained_contract': str(f), 'required_parent': str(path)})
    files = [f for d in candidates for f in d.rglob('*') if f.is_file()]
    plan = {'project': str(ROOT), 'targets': list(map(str, candidates)), 'files': len(files),
            'bytes': sum(f.stat().st_size for f in files), 'blockers': blockers,
            'keep': ['raw datasets, base prepared arrays except obsolete run duplicates',
                     'round2 main and DDoS chain; latest selected Hulk/Portscan baseline chains',
                     'cicunsw_zero_day_v2 main and incomplete latest LOACO chain',
                     'historical research_rounds/loaco_finetune summaries and logs',
                     'code/config/docs/reference PDFs/.venv/.git']}
    print(json.dumps(plan, ensure_ascii=False, indent=2), flush=True)
    if blockers:
        raise RuntimeError('Retained artifact depends on cleanup targets; no backup/deletion allowed')
    if not a.archive_dir:
        return
    destination = Path(a.archive_dir).resolve()
    if destination.exists() or inside(destination, ROOT):
        raise RuntimeError('Backup must be a new directory outside the project')
    destination.mkdir(parents=True)
    archive = destination/'retired_artifacts.zip'
    records = []
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=1, allowZip64=True) as z:
        for index, f in enumerate(files):
            relative = f.relative_to(ROOT).as_posix()
            h = hashlib.sha256()
            with f.open('rb') as source, z.open(relative, 'w', force_zip64=True) as output:
                for block in iter(lambda: source.read(8*1024*1024), b''):
                    h.update(block); output.write(block)
            records.append({'path': relative, 'bytes': f.stat().st_size, 'sha256': h.hexdigest()})
            if index % 100 == 0:
                print(f'Archived {index+1}/{len(files)}', flush=True)
    with zipfile.ZipFile(archive) as z:
        if set(z.namelist()) != {r['path'] for r in records}:
            raise RuntimeError('Archive member set mismatch')
        for r in records:
            h = hashlib.sha256()
            with z.open(r['path']) as stream:
                for block in iter(lambda: stream.read(8*1024*1024), b''):
                    h.update(block)
            if h.hexdigest() != r['sha256']:
                raise RuntimeError(f'Archive verification failed: {r["path"]}')
    receipt = {**plan, 'archive': str(archive), 'verified': True,
               'verified_utc': datetime.now(timezone.utc).isoformat(), 'file_manifest': records}
    (destination/'verified_manifest.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'VERIFIED_BACKUP={destination}', flush=True)


if __name__ == '__main__':
    main()
