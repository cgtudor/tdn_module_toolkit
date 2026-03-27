import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { creaturesApi } from '@/lib/api';
import { CreatureDetail, CreatureListResponse } from '@/types/creature';

export function useCreatureList(params: { offset?: number; limit?: number }) {
  return useQuery<CreatureListResponse>({
    queryKey: ['creatures', 'list', params],
    queryFn: () => creaturesApi.list(params) as Promise<CreatureListResponse>,
  });
}

export function useCreatureSearch(query: string, enabled = true) {
  return useQuery<{ creatures: CreatureDetail[]; total: number }>({
    queryKey: ['creatures', 'search', query],
    queryFn: () => creaturesApi.search(query) as Promise<{ creatures: CreatureDetail[]; total: number }>,
    enabled: enabled && query.length > 0,
  });
}

export function useCreature(resref: string | null) {
  return useQuery<CreatureDetail>({
    queryKey: ['creatures', 'detail', resref],
    queryFn: () => creaturesApi.get(resref!) as Promise<CreatureDetail>,
    enabled: !!resref,
  });
}

export function useSetEquipment() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ resref, slotId, itemResref }: { resref: string; slotId: number; itemResref: string }) =>
      creaturesApi.setEquipment(resref, slotId, itemResref),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['creatures', 'detail', variables.resref] });
    },
  });
}

export function useRemoveEquipment() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ resref, slotId }: { resref: string; slotId: number }) =>
      creaturesApi.removeEquipment(resref, slotId),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['creatures', 'detail', variables.resref] });
    },
  });
}

export function useAddInventory() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ resref, itemResref, stackSize }: { resref: string; itemResref: string; stackSize?: number }) =>
      creaturesApi.addInventory(resref, itemResref, stackSize),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['creatures', 'detail', variables.resref] });
    },
  });
}

export function useRemoveInventory() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ resref, index }: { resref: string; index: number }) =>
      creaturesApi.removeInventory(resref, index),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['creatures', 'detail', variables.resref] });
    },
  });
}
