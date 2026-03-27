import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { areasApi, systemApi, searchApi } from '@/lib/api';
import { AreaListResponse, StoreInstance, CreatureInstance, SyncResult, GlobalSearchResponse } from '@/types/gff';

export function useAreaList(params: { offset?: number; limit?: number }) {
  return useQuery<AreaListResponse>({
    queryKey: ['areas', 'list', params],
    queryFn: () => areasApi.list(params) as Promise<AreaListResponse>,
  });
}

export function useAreaSearch(query: string, limit = 50) {
  return useQuery<AreaListResponse>({
    queryKey: ['areas', 'search', query, limit],
    queryFn: () => areasApi.search(query, limit) as Promise<AreaListResponse>,
    enabled: query.length > 0,
  });
}

export function useArea(resref: string | null) {
  return useQuery({
    queryKey: ['areas', 'detail', resref],
    queryFn: () => areasApi.get(resref!),
    enabled: !!resref,
  });
}

export function useAreaStores(resref: string | null) {
  return useQuery({
    queryKey: ['areas', 'stores', resref],
    queryFn: () => areasApi.listStores(resref!),
    enabled: !!resref,
  });
}

export function useAreaStore(areaResref: string | null, index: number | null) {
  return useQuery<StoreInstance>({
    queryKey: ['areas', 'store', areaResref, index],
    queryFn: () => areasApi.getStore(areaResref!, index!) as Promise<StoreInstance>,
    enabled: !!areaResref && index !== null,
  });
}

export function useAreaCreatures(resref: string | null) {
  return useQuery({
    queryKey: ['areas', 'creatures', resref],
    queryFn: () => areasApi.listCreatures(resref!),
    enabled: !!resref,
  });
}

export function useAreaCreature(areaResref: string | null, index: number | null) {
  return useQuery<CreatureInstance>({
    queryKey: ['areas', 'creature', areaResref, index],
    queryFn: () => areasApi.getCreature(areaResref!, index!) as Promise<CreatureInstance>,
    enabled: !!areaResref && index !== null,
  });
}

export function useSyncStoreFromTemplate() {
  const queryClient = useQueryClient();

  return useMutation<SyncResult, Error, { areaResref: string; index: number }>({
    mutationFn: ({ areaResref, index }) => areasApi.syncStore(areaResref, index),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['areas', 'store', variables.areaResref, variables.index] });
    },
  });
}

export function useUpdateAreaStoreSettings() {
  const queryClient = useQueryClient();

  return useMutation<
    { success: boolean; message: string; changes: string[] },
    Error,
    {
      areaResref: string;
      storeIndex: number;
      settings: {
        markup?: number;
        markdown?: number;
        max_buy_price?: number;
        store_gold?: number;
        identify_price?: number;
        black_market?: boolean;
        bm_markdown?: number;
        will_not_buy?: number[];
        will_only_buy?: number[];
      };
    }
  >({
    mutationFn: ({ areaResref, storeIndex, settings }) =>
      areasApi.updateStoreSettings(areaResref, storeIndex, settings),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['areas', 'store', variables.areaResref, variables.storeIndex] });
    },
  });
}

export function useAddAreaStoreItemAuto() {
  const queryClient = useQueryClient();

  return useMutation<
    {
      success: boolean;
      item_resref: string;
      category_id: number;
      category_name: string;
      base_item: number;
      store_panel: number | null;
    },
    Error,
    { areaResref: string; storeIndex: number; itemResref: string; infinite?: boolean }
  >({
    mutationFn: ({ areaResref, storeIndex, itemResref, infinite }) =>
      areasApi.addStoreItemAuto(areaResref, storeIndex, itemResref, infinite),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['areas', 'store', variables.areaResref, variables.storeIndex] });
    },
  });
}

export function useAddAreaStoreItem() {
  const queryClient = useQueryClient();

  return useMutation<
    { success: boolean; item_resref: string },
    Error,
    { areaResref: string; storeIndex: number; categoryId: number; itemResref: string; infinite?: boolean }
  >({
    mutationFn: ({ areaResref, storeIndex, categoryId, itemResref, infinite }) =>
      areasApi.addStoreItem(areaResref, storeIndex, categoryId, itemResref, infinite),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['areas', 'store', variables.areaResref, variables.storeIndex] });
    },
  });
}

export function useUpdateAreaStoreItem() {
  const queryClient = useQueryClient();

  return useMutation<
    { success: boolean },
    Error,
    {
      areaResref: string;
      storeIndex: number;
      categoryId: number;
      itemIndex: number;
      infinite?: boolean;
      stack_size?: number;
      repos_x?: number;
      repos_y?: number;
    }
  >({
    mutationFn: ({ areaResref, storeIndex, categoryId, itemIndex, infinite, stack_size, repos_x, repos_y }) =>
      areasApi.updateStoreItem(areaResref, storeIndex, categoryId, itemIndex, { infinite, stack_size, repos_x, repos_y }),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['areas', 'store', variables.areaResref, variables.storeIndex] });
    },
  });
}

export function useRemoveAreaStoreItem() {
  const queryClient = useQueryClient();

  return useMutation<
    { success: boolean; index: number },
    Error,
    { areaResref: string; storeIndex: number; categoryId: number; itemIndex: number }
  >({
    mutationFn: ({ areaResref, storeIndex, categoryId, itemIndex }) =>
      areasApi.removeStoreItem(areaResref, storeIndex, categoryId, itemIndex),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['areas', 'store', variables.areaResref, variables.storeIndex] });
    },
  });
}

export function useSystemStatus() {
  return useQuery({
    queryKey: ['system', 'status'],
    queryFn: () => systemApi.status(),
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) {
        return 2000;
      }
      // Poll frequently during transitional states
      if (data.state === 'initializing' || data.state === 'indexing' ||
          data.state === 'needs_configuration' || data.state === 'error' || data.indexing) {
        return 1500;
      }
      // Once connected and ready, refresh every 30 seconds
      return 30000;
    },
    retry: true,
    retryDelay: 2000,
  });
}

export function useReindex() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => systemApi.reindex(),
    onSuccess: () => {
      // Invalidate all cached data
      queryClient.invalidateQueries();
    },
  });
}

export function useGlobalSearch(query: string, enabled = true) {
  return useQuery<GlobalSearchResponse>({
    queryKey: ['search', 'global', query],
    queryFn: () => searchApi.global(query) as Promise<GlobalSearchResponse>,
    enabled: enabled && query.length > 0,
  });
}
