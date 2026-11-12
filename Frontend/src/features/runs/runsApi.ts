import { baseApi } from '../../shared/api/baseApi';
import { detailedMessage, messageOf } from '../../shared/api/errors';

type Rec = Record<string, unknown>;

export interface SavedRun {
  id: number;
  label: string;
  createdAt: string | null;
  datasetId: string | null;
  siteId: string | null;
  survives: boolean | null;
  plan: Rec;
  result: Rec;
}

export interface RunsPage {
  runs: SavedRun[];
  count: number | null;
  hasNext: boolean;
  hasPrev: boolean;
}

export interface SaveRunArgs {
  dataset_id: string;
  site_id: string;
  plan: Rec;
  result: Rec;
  label?: string;
}

const rec = (v: unknown): Rec =>
  typeof v === 'object' && v !== null && !Array.isArray(v) ? (v as Rec) : {};
const str = (v: unknown): string | null =>
  typeof v === 'string' && v ? v : typeof v === 'number' ? String(v) : null;

export function parseRun(raw: unknown): SavedRun | null {
  const r = rec(raw);
  const id = typeof r.id === 'number' ? r.id : Number(r.id);
  if (!Number.isFinite(id)) return null;
  const result = rec(r.result);
  return {
    id,
    label: str(r.label) ?? '',
    createdAt: str(r.created_at) ?? str(r.created),
    datasetId: str(r.dataset_id) ?? str(r.dataset),
    siteId: str(r.site_id) ?? str(r.site),
    survives: typeof result.survives === 'boolean' ? result.survives : null,
    plan: rec(r.plan),
    result,
  };
}

export function parseRunsPage(raw: unknown): RunsPage {
  const body = rec(raw);
  const list = Array.isArray(raw) ? raw : Array.isArray(body.results) ? body.results : [];
  return {
    runs: list.flatMap((item) => {
      const run = parseRun(item);
      return run ? [run] : [];
    }),
    count: typeof body.count === 'number' ? body.count : null,
    hasNext: typeof body.next === 'string' && body.next.length > 0,
    hasPrev: typeof body.previous === 'string' && body.previous.length > 0,
  };
}

export const runsApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    listRuns: build.query<RunsPage, number>({
      query: (page) => `/runs/?page=${page}`,
      transformResponse: parseRunsPage,
      providesTags: ['Runs'],
    }),
    saveRun: build.mutation<SavedRun | null, SaveRunArgs>({
      query: (body) => ({ url: '/runs/', method: 'POST', body }),
      transformResponse: parseRun,
      transformErrorResponse: (error) => ({ status: 'CUSTOM_ERROR' as const, error: detailedMessage(error) }),
      invalidatesTags: ['Runs'],
    }),
    renameRun: build.mutation<SavedRun | null, { id: number; label: string }>({
      query: ({ id, label }) => ({ url: `/runs/${id}/`, method: 'PATCH', body: { label } }),
      transformResponse: parseRun,
      transformErrorResponse: (error) => ({ status: 'CUSTOM_ERROR' as const, error: messageOf(error) }),
      invalidatesTags: ['Runs'],
    }),
    deleteRun: build.mutation<null, number>({
      query: (id) => ({ url: `/runs/${id}/`, method: 'DELETE' }),
      transformResponse: () => null,
      transformErrorResponse: (error) => ({ status: 'CUSTOM_ERROR' as const, error: messageOf(error) }),
      invalidatesTags: ['Runs'],
    }),
  }),
});

export const {
  useListRunsQuery,
  useSaveRunMutation,
  useRenameRunMutation,
  useDeleteRunMutation,
} = runsApi;
