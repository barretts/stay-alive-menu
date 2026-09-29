"""Package the static viewer and its media for GitHub Pages, using only stdlib.

The publish directory is an explicit collection of runtime assets and linked
archive documents. Original/extracted media, caches, and utilities are omitted.
"""
import argparse
import json
import pathlib
import shutil


ROOT=pathlib.Path(__file__).resolve().parent.parent
DOCUMENTS=('index.html','menu-navigation.js','README.md','Menu-Map.md',
           'assets.csv','buttons.csv','manifest.json','navigation-map.json',
           'validation.json')


def site_files():
    archive=json.loads((ROOT/'manifest.json').read_text(encoding='utf-8'))
    files={pathlib.Path(name) for name in DOCUMENTS}
    files.update(path.relative_to(ROOT) for path in ROOT.glob('contact-sheet-*.jpg'))
    for asset in archive['assets']:
        folder=pathlib.Path(asset['path'])
        files.update(folder/name for name in ('preview.mp4','preview.jpg','buttons.jpg'))
        for graphic in asset['graphics']:
            files.add(folder/graphic['normal'])
            files.update(folder/highlight['file'] for highlight in graphic['highlights'])
    for relative in files:
        source=(ROOT/relative).resolve()
        if not source.is_relative_to(ROOT) or not source.is_file():
            raise ValueError('Missing or invalid site asset: '+str(relative))
    return files


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',default='_site',help='New output directory within this repository')
    args=parser.parse_args()
    output=(ROOT/args.out).resolve()
    if output==ROOT or not output.is_relative_to(ROOT):
        parser.error('Output must be a new directory within this repository')
    files=site_files()
    # A new directory prevents stale or unrelated files from being published.
    output.mkdir(parents=True,exist_ok=False)
    total=0
    for relative in sorted(files):
        target=output/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(ROOT/relative,target)
        total+=target.stat().st_size
    (output/'.nojekyll').touch()
    print(json.dumps({'output':str(output),'files':len(files)+1,'bytes':total}),flush=True)


if __name__=='__main__':main()
