import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { storesApi } from '@/lib/api';
import { StoreDetail, StoreListResponse, StoreItemAddResult } from '@/types/store';

export function useStoreList(params: { offset?: number; limit?: number }) {
  return useQuery<StoreListResponse>({
    queryKey: ['stores', 'list', params],
    queryFn: () => storesApi.list(params) as Promise<StoreListResponse>,
  });
}

export function useStoreSearch(query: string, enabled = true) {
  return useQuery<{ stores: StoreDetail[]; total: number }>({
    queryKey: ['stores', 'search', query],
    queryFn: () => storesApi.search(query) as Promise<{ stores: StoreDetail[]; total: number }>,
    enabled: enabled && query.length > 0,
  });
}

export function useStore(resref: string | null) {
  return useQuery<StoreDetail>({
    queryKey: ['stores', 'detail', resref],
    queryFn: () => storesApi.get(resref!) as Promise<StoreDetail>,
    enabled: !!resref,
  });
}

export function useUpdateStoreSettings() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ resref, settings }: { resref: string; settings: Record<string, unknown> }) =>
      storesApi.updateSettings(resref, settings),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['stores', 'detail', variables.resref] });
    },
  });
}

export function useAddStoreItemAuto() {
  const queryClient = useQueryClient();

  return useMutation<StoreItemAddResult, Error, {
    resref: string;
    itemResref: string;
    infinite?: boolean;
    stackSize?: number;
  }>({
    mutationFn: ({
      resref,
      itemResref,
      infinite,
      stackSize,
    }) => storesApi.addItemAuto(resref, itemResref, infinite, stackSize),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['stores', 'detail', variables.resref] });
    },
  });
}

export function useAddStoreItem() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      resref,
      categoryId,
      itemResref,
      infinite,
      stackSize,
    }: {
      resref: string;
      categoryId: number;
      itemResref: string;
      infinite?: boolean;
      stackSize?: number;
    }) => storesApi.addItem(resref, categoryId, itemResref, infinite, stackSize),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['stores', 'detail', variables.resref] });
    },
  });
}

export function useUpdateStoreItem() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      resref,
      categoryId,
      index,
      updates,
    }: {
      resref: string;
      categoryId: number;
      index: number;
      updates: { infinite?: boolean; stack_size?: number; repos_x?: number; repos_y?: number };
    }) => storesApi.updateItem(resref, categoryId, index, updates),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['stores', 'detail', variables.resref] });
    },
  });
}

export function useRemoveStoreItem() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ resref, categoryId, index }: { resref: string; categoryId: number; index: number }) =>
      storesApi.removeItem(resref, categoryId, index),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['stores', 'detail', variables.resref] });
    },
  });
}
