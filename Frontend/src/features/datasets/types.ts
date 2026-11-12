export interface DatasetInfo {
  id: string;
  label: string;
  mode: string | null;
}

export interface SiteInfo {
  id: string;
  label: string;
  latitude: number | null;
  longitude: number | null;
  horizon: number[] | null;
  sky: SkyTrack | null;
}

export interface SkyTrack {
  startMs: number;
  stepMs: number;
  sunAz: (number | null)[];
  sunEl: (number | null)[];
  earthAz: (number | null)[];
  earthEl: (number | null)[];
}

export interface SourceItem {
  title: string;
  text: string | null;
}

export interface Provenance {
  mode: string | null;
  sources: SourceItem[];
}

export interface CheckItem {
  name: string;
  status: 'pass' | 'fail' | 'pending';
}

export interface Validation {
  checks: CheckItem[];
}
