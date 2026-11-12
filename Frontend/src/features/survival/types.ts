import { z } from 'zod';
import type { Say } from '../../shared/i18n';
import type { FailureReason, Result } from '../result/types';

export interface SurvivalArgs {
  latitude: number;
  longitude: number;
  start: string;
  landing: string;
}

export const rawResponseSchema = z.object({ status: z.enum(['SUCCESS', 'FAIL']) }).loose();
export type RawResponse = z.infer<typeof rawResponseSchema>;

export interface Suggestion {
  latitude: number;
  longitude: number;
}

export interface DateSuggestion extends Suggestion {
  start: string;
  landing: string;
}

export type FixResult =
  | { kind: 'coords'; coord: Suggestion }
  | { kind: 'date'; offer: DateSuggestion };

export type SectionId =
  | 'coordinates'
  | 'slope'
  | 'illumination'
  | 'thermal'
  | 'battery'
  | 'timeline'
  | 'regolith'
  | 'safeHaven'
  | 'config'
  | 'other';

export interface Assumption {
  title: Say | null;
  text: Say;
}

export interface DataSection {
  id: SectionId;
  title: Say;
  data: unknown;
}

export interface SurvivalResult {
  survives: boolean;
  assumptions: Assumption[];
  sections: DataSection[];
  sim: Result | null;
  reason: FailureReason | null;
  marginPct: number | null;
}

export interface SurvivalOutcome {
  result: SurvivalResult;
}

export type SiteStatus = 'loading' | 'ok' | 'fail' | 'north' | 'error';

export interface SiteSurvival {
  status: SiteStatus;
  survives: boolean | null;
  result: SurvivalResult | null;
  message: string | null;
}
