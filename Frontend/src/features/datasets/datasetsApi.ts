import { baseApi } from '../../shared/api/baseApi';
import { parseDatasets, parseProvenance, parseSites, parseValidation, pickDataset } from './parse';
import type { DatasetInfo, Provenance, SiteInfo, Validation } from './types';

export const DEMO_DATASET_URL = `${import.meta.env.BASE_URL}demo-dataset.json`;

export interface DatasetList {
  datasets: DatasetInfo[];
  active: DatasetInfo | null;
}

export const datasetsApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    getDatasets: build.query<DatasetList, void>({
      query: () => '/datasets/',
      transformResponse: (raw: unknown): DatasetList => {
        const datasets = parseDatasets(raw);
        return { datasets, active: pickDataset(raw, datasets) };
      },
      providesTags: ['Dataset'],
    }),
    getDatasetProvenance: build.query<Provenance, string>({
      query: (id) => `/datasets/${encodeURIComponent(id)}/provenance/`,
      transformResponse: parseProvenance,
      providesTags: ['Dataset'],
    }),
    getDatasetSites: build.query<SiteInfo[], string>({
      query: (id) => `/datasets/${encodeURIComponent(id)}/sites/`,
      transformResponse: parseSites,
      providesTags: ['Dataset'],
    }),
    getDemoSites: build.query<SiteInfo[], void>({
      query: () => ({
        url: new URL(DEMO_DATASET_URL, globalThis.location?.href ?? 'http://localhost/').href,
        credentials: 'omit',
      }),
      transformResponse: parseSites,
    }),
    getDatasetValidation: build.query<Validation, string>({
      query: (id) => `/datasets/${encodeURIComponent(id)}/validation/`,
      transformResponse: parseValidation,
      providesTags: ['Dataset'],
    }),
  }),
});

export const {
  useGetDatasetsQuery,
  useGetDemoSitesQuery,
  useGetDatasetSitesQuery,
  useGetDatasetProvenanceQuery,
  useGetDatasetValidationQuery,
} = datasetsApi;
