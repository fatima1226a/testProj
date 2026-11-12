import { skipToken } from '@reduxjs/toolkit/query';
import { messageOf } from '../../shared/api/errors';
import {
  useGetDatasetProvenanceQuery,
  useGetDatasetSitesQuery,
  useGetDatasetsQuery,
  useGetDemoSitesQuery,
  useGetDatasetValidationQuery,
} from './datasetsApi';
import type { DatasetInfo, Provenance, SiteInfo, Validation } from './types';

export interface DatasetContext {
  dataset: DatasetInfo | null;
  provenance: Provenance | null;
  validation: Validation | null;
  sites: SiteInfo[] | null;
  horizonSites: SiteInfo[] | null;
  sitesSettled: boolean;
  loading: boolean;
  error: string | null;
}

export function useDataset(): DatasetContext {
  const list = useGetDatasetsQuery();
  const dataset = list.data?.active ?? null;
  const arg = dataset?.id ?? skipToken;
  const provenance = useGetDatasetProvenanceQuery(arg);
  const validation = useGetDatasetValidationQuery(arg);
  const sites = useGetDatasetSitesQuery(arg);
  const serverSites = sites.data?.some((s) => s.horizon !== null) ? sites.data : null;
  const serverSettled = !list.isLoading && (dataset === null || (!sites.isLoading && !sites.isUninitialized));
  const demo = useGetDemoSitesQuery(undefined, { skip: !serverSettled || serverSites !== null });
  return {
    horizonSites: serverSites ?? demo.data ?? null,
    dataset,
    provenance: provenance.data ?? null,
    validation: validation.data ?? null,
    sites: sites.data ?? null,
    sitesSettled: dataset !== null && !sites.isLoading && !sites.isUninitialized,
    loading: list.isLoading || provenance.isLoading || validation.isLoading,
    error: list.isError ? messageOf(list.error) : null,
  };
}
