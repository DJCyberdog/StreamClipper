"""Explicit download of supported model presets, never called during analysis."""
from __future__ import annotations

import argparse
from pathlib import Path
from streamclipper.portable import configure_portable_environment
configure_portable_environment()
from streamclipper.model_catalog import DEFAULTS, PRESETS, download_preset, preset, presets_for
from streamclipper.semantic import default_models_directory


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description='Lade ausgewählte KI-Modelle nur nach ausdrücklichem Aufruf.')
    parser.add_argument('--which', choices=['speech', 'vision', 'detector', 'both', 'all'], default='both')
    parser.add_argument('--model', choices=[m.id for m in PRESETS],
                        help='Eine konkrete Modellvariante statt nur der Standardmodelle laden')
    parser.add_argument('--list', action='store_true', help='Alle unterstützten Modelle anzeigen')
    parser.add_argument('--directory', type=Path, default=default_models_directory())
    opts = parser.parse_args(argv)
    if opts.list:
        for m in PRESETS:
            print(f'{m.kind:9s} {m.id:25s} {m.label} ({m.repository})')
        return
    if opts.model:
        selected = [opts.model]
    else:
        kinds = ['speech', 'vision'] if opts.which == 'both' else (
            list(DEFAULTS) if opts.which == 'all' else [opts.which])
        selected = [DEFAULTS[k] for k in kinds]
    for model_id in selected:
        item = preset(model_id)
        print(f'Installiere {item.label} ({item.repository}) nach {opts.directory / item.folder} …', flush=True)
        folder = download_preset(model_id, opts.directory)
        print(f'Bereit und geprüft: {folder}', flush=True)
    print('Die Videoanalyse benötigt keine Internetverbindung.')


if __name__ == '__main__':
    main()
