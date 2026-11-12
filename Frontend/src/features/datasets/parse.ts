import type { CheckItem, DatasetInfo, Provenance, SiteInfo, SkyTrack, SourceItem, Validation } from './types';

type Rec = Record<string, unknown>;

const rec = (v: unknown): Rec =>
  typeof v === 'object' && v !== null && !Array.isArray(v) ? (v as Rec) : {};
const str = (v: unknown): string | null =>
  typeof v === 'string' && v.trim() ? v : typeof v === 'number' ? String(v) : null;

function listOf(raw: unknown, keys: string[]): unknown[] {
  if (Array.isArray(raw)) return raw;
  const body = rec(raw);
  for (const key of keys) {
    const value = body[key];
    if (Array.isArray(value)) return value;
  }
  return [];
}

const DATASET_ID = ['id', 'dataset_id', 'datasetId', 'slug', 'name', 'version'];

function datasetItems(raw: unknown): unknown[] {
  const listed = listOf(raw, ['results', 'datasets', 'items']);
  if (listed.length > 0 || Array.isArray(raw)) return listed;
  const body = rec(raw);
  return str(pick(body, DATASET_ID)) ? [body] : [];
}

const pick = (source: Rec, keys: string[]): unknown => {
  for (const key of keys) if (source[key] !== undefined && source[key] !== null) return source[key];
  return undefined;
};

export function parseDatasets(raw: unknown): DatasetInfo[] {
  return datasetItems(raw).flatMap((item) => {
    const r = rec(item);
    const id = str(pick(r, DATASET_ID));
    if (!id) return [];
    return [{ id, label: str(pick(r, ['name', 'title', 'label'])) ?? id, mode: str(r.mode) }];
  });
}

export function pickDataset(raw: unknown, datasets: DatasetInfo[]): DatasetInfo | null {
  const flagged = datasetItems(raw).find((item) => {
    const r = rec(item);
    return ['is_default', 'default', 'is_active', 'is_latest', 'latest'].some((k) => r[k] === true);
  });
  if (flagged) {
    const id = str(pick(rec(flagged), DATASET_ID));
    const found = datasets.find((d) => d.id === id);
    if (found) return found;
  }
  return datasets[0] ?? null;
}

export function parseProvenance(raw: unknown): Provenance {
  const body = rec(raw);
  const sources: SourceItem[] = listOf(body, ['sources', 'datasets', 'items']).flatMap((item) => {
    if (typeof item === 'string') return [{ title: item, text: null }];
    const r = rec(item);
    const title = str(pick(r, ['name', 'title', 'source', 'id']));
    if (!title) return [];
    return [{ title, text: str(pick(r, ['description', 'text', 'note', 'usage'])) }];
  });
  return { mode: str(body.mode), sources };
}

function checkStatus(value: unknown): CheckItem['status'] {
  if (value === true) return 'pass';
  if (value === false) return 'fail';
  const text = typeof value === 'string' ? value.toLowerCase() : '';
  if (['pass', 'passed', 'ok', 'success', 'done'].includes(text)) return 'pass';
  if (['fail', 'failed', 'error'].includes(text)) return 'fail';
  return 'pending';
}

export function parseValidation(raw: unknown): Validation {
  const listed = listOf(raw, ['checks', 'results', 'items']);
  if (listed.length > 0) {
    return {
      checks: listed.flatMap((item) => {
        const r = rec(item);
        const name = str(pick(r, ['name', 'title', 'check', 'id']));
        return name ? [{ name, status: checkStatus(pick(r, ['status', 'passed', 'result'])) }] : [];
      }),
    };
  }
  const body = rec(raw);
  return {
    checks: Object.entries(body).flatMap(([name, value]) =>
      typeof value === 'object' && value !== null && !Array.isArray(value)
        ? [{ name, status: checkStatus(rec(value).status) }]
        : typeof value === 'string' || typeof value === 'boolean'
          ? [{ name, status: checkStatus(value) }]
          : [],
    ),
  };
}

const numOf = (v: unknown): number | null => {
  const n = typeof v === 'string' && v.trim() ? Number(v) : v;
  return typeof n === 'number' && Number.isFinite(n) ? n : null;
};

function horizonOf(value: unknown): number[] | null {
  if (!Array.isArray(value) || value.length === 0) return null;
  const out: number[] = [];
  for (const item of value) {
    const n = numOf(item);
    if (n === null) return null;
    out.push(n);
  }
  return out;
}

function skyOf(hours: unknown, stepMinutes: number | null, startIso: string | null): SkyTrack | null {
  if (!Array.isArray(hours) || hours.length === 0) return null;
  const rows = hours.map(rec);
  const firstMs = Date.parse(str(rows[0]?.t) ?? startIso ?? '');
  if (!Number.isFinite(firstMs)) return null;
  const secondMs = rows.length > 1 ? Date.parse(str(rows[1]?.t) ?? '') : NaN;
  const stepMs =
    stepMinutes !== null && stepMinutes > 0
      ? stepMinutes * 60_000
      : Number.isFinite(secondMs) && secondMs > firstMs
        ? secondMs - firstMs
        : null;
  if (stepMs === null) return null;
  const col = (key: string) => rows.map((r) => numOf(r[key]));
  return { startMs: firstMs, stepMs, sunAz: col('sunAz'), sunEl: col('sunEl'), earthAz: col('earthAz'), earthEl: col('earthEl') };
}

export function parseSites(raw: unknown): SiteInfo[] {
  const win = rec(rec(raw).window);
  const winStep = numOf(win.stepMinutes);
  const winStart = str(win.start);
  return listOf(raw, ['results', 'sites', 'items']).flatMap((item) => {
    const r = rec(item);
    const id = str(pick(r, ['id', 'site_id', 'slug', 'code', 'name']));
    if (!id) return [];
    const coord = rec(r.coordinates ?? r.coord ?? r.location);
    return [
      {
        id,
        label: str(pick(r, ['name', 'title', 'label'])) ?? id,
        latitude: numOf(pick(r, ['latitude', 'lat']) ?? pick(coord, ['latitude', 'lat'])),
        longitude: numOf(pick(r, ['longitude', 'lon', 'lng']) ?? pick(coord, ['longitude', 'lon', 'lng'])),
        horizon: horizonOf(pick(r, ['horizon', 'horizon_profile', 'horizonProfile', 'horizon_deg'])),
        sky: skyOf(r.hours, numOf(r.stepMinutes) ?? winStep, winStart),
      },
    ];
  });
}

const rad = (deg: number) => (deg * Math.PI) / 180;

export function pickSite(sites: SiteInfo[], coord: { latDeg: number; lonDeg: number }): SiteInfo | null {
  let best: SiteInfo | null = null;
  let bestDistance = Infinity;
  for (const site of sites) {
    if (site.latitude === null || site.longitude === null) continue;
    const dLat = rad(site.latitude - coord.latDeg);
    const dLon = rad(site.longitude - coord.lonDeg);
    const h =
      Math.sin(dLat / 2) ** 2 +
      Math.cos(rad(coord.latDeg)) * Math.cos(rad(site.latitude)) * Math.sin(dLon / 2) ** 2;
    const distance = 2 * Math.asin(Math.min(1, Math.sqrt(h)));
    if (distance < bestDistance) {
      best = site;
      bestDistance = distance;
    }
  }
  return best ?? sites[0] ?? null;
}
