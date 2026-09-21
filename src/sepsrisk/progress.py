from __future__ import annotations

from dataclasses import dataclass
import sys
import time

try:
    from tqdm.auto import tqdm
except Exception:  # pragma: no cover
    tqdm = None


class _NullBar:
    def update(self, *_args, **_kwargs): return None
    def close(self): return None
    def set_description_str(self, *_args, **_kwargs): return None
    def set_postfix_str(self, *_args, **_kwargs): return None
    def refresh(self): return None


@dataclass
class ProgressConfig:
    enabled: bool = True
    show_download_bytes: bool = True
    show_row_progress: bool = True
    leave_completed: bool = True


class PipelineProgress:
    """Colab-friendly progress with global stage + nested byte/row bars."""

    def __init__(self, cfg: dict | None = None, enabled: bool | None = None):
        raw = cfg or {}
        self.cfg = ProgressConfig(
            enabled=bool(raw.get('enabled', True) if enabled is None else enabled),
            show_download_bytes=bool(raw.get('show_download_bytes', True)),
            show_row_progress=bool(raw.get('show_row_progress', True)),
            leave_completed=bool(raw.get('leave_completed', True)),
        )
        self.started = time.time()
        self.value = 0.0
        self._last_text = None
        self.bar = _NullBar()
        if self.cfg.enabled and tqdm is not None:
            self.bar = tqdm(
                total=100, initial=0, desc='SEPS · preparando', unit='%',
                dynamic_ncols=True, leave=self.cfg.leave_completed,
                bar_format='{l_bar}{bar}| {n:5.1f}/{total_fmt}% [{elapsed}<{remaining}, {rate_fmt}] {postfix}',
            )

    @property
    def enabled(self): return self.cfg.enabled

    def set(self, value: float, stage: str, detail: str | None = None):
        value = max(self.value, min(100.0, float(value)))
        if tqdm is not None and not isinstance(self.bar, _NullBar):
            delta = value - self.value
            if delta: self.bar.update(delta)
            self.bar.set_description_str(f'SEPS · {stage}')
            self.bar.set_postfix_str(detail or '', refresh=True)
        elif self.cfg.enabled:
            text = f'[{value:5.1f}%] {stage}' + (f' · {detail}' if detail else '')
            if text != self._last_text:
                print(f'{text} · {time.time()-self.started:,.1f}s', file=sys.stdout, flush=True)
                self._last_text = text
        self.value = value

    def note(self, stage: str, detail: str | None = None):
        self.set(self.value, stage, detail)

    def discovery(self, done: int, total: int, detail: str | None = None):
        frac = 1.0 if total <= 0 else min(1.0, done / total)
        self.set(5 + 15 * frac, 'descubriendo fuentes', detail)

    def ingestion(self, done: int, total: int, detail: str | None = None):
        frac = 1.0 if total <= 0 else min(1.0, done / total)
        self.set(20 + 50 * frac, 'ingiriendo EEFF', detail)

    def _task_bar(self, total, label, unit, unit_scale=False):
        if not self.cfg.enabled or tqdm is None: return _NullBar()
        return tqdm(
            total=total, desc=f'  ↳ {label}', unit=unit, unit_scale=unit_scale,
            dynamic_ncols=True, leave=False,
            bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}] {postfix}',
        )

    def byte_bar(self, total_bytes: int | None, label: str):
        if not self.cfg.show_download_bytes: return _NullBar()
        return self._task_bar(int(total_bytes or 0) or None, label, 'B', True)

    def row_bar(self, total_rows: int | None, label: str):
        if not self.cfg.show_row_progress: return _NullBar()
        return self._task_bar(int(total_rows or 0) or None, label, 'filas', False)

    def close(self, ok: bool = True, detail: str | None = None):
        if ok:
            self.set(100, 'completo', detail or 'OK')
        elif tqdm is not None and not isinstance(self.bar, _NullBar):
            self.bar.set_description_str('SEPS · ERROR')
            if detail: self.bar.set_postfix_str(detail, refresh=True)
        self.bar.close()
